import sqlite3
import os
import random
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, g, session
from flask_socketio import SocketIO, emit, join_room
from flask_mail import Mail, Message
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'sphinx of black quartz judge my vow'
DB_NAME = 'queue_system.db'
socketio = SocketIO(app, cors_allowed_origins="*")

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
mail = Mail(app)

def send_verification_email(email, code):
    """Send a 6-digit verification code to the given email.
    Returns True if it sent successfully, False otherwise (and logs the error)."""
    try:
        msg = Message('Verify your Queues account', recipients=[email])
        msg.body = f'Your verification code is: {code}'
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        return False

def get_db_connection():
    if 'db' not in g:
        # Adding timeout=20 gives SQLite 20 seconds to wait for open locks before raising an error
        g.db = sqlite3.connect(DB_NAME, timeout=20)
        g.db.row_factory = sqlite3.Row
    return g.db

def create_notification(user_id, message):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO notification (user_id, message) VALUES (?, ?)",
        (user_id, message)
    )
    conn.commit()

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = get_db_connection()
    with open('schema.sql') as f:
        conn.executescript(f.read())
    conn.commit()

def create_admin():
    conn = get_db_connection()

    existing_admin = conn.execute(
        'SELECT * FROM user WHERE username = ?',
        ('admin',)
    ).fetchone()

    if not existing_admin:
        conn.execute(
            '''
            INSERT INTO user (username, password, role, is_verified)
            VALUES (?, ?, ?, ?)
            ''',
            ('admin', 'admin123', 'ADMIN', 1)
        )
        conn.commit()
        print("Admin account created.")


@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'ADMIN':
        return redirect(url_for('login'))

    return render_template('admin_dashboard.html')

def admin_required():
    return session.get('role') == 'ADMIN' and session.get('user_id') is not None

@app.route('/staff/dashboard/<int:store_id>')
def staff_dashboard(store_id):

    # Only STAFF can access Staff Dashboard
    if session.get('role') != 'STAFF':
        return redirect(url_for('login'))

    conn = get_db_connection()

    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE store_id = ?
        AND owner_id = ?
        """,
        (
            store_id,
            session['user_id']
        )
    ).fetchone()

    if not store:
        return "You do not have access to this store.", 403

    if store['store_status'] != 'APPROVED':
        return redirect(url_for('staff_status'))

    return render_template(
        'staff_dashboard.html',
        store_id=store_id
    )
    

#======================================================================
# -- Member 1 (Syahmi): User & Store Api
#======================================================================


# =========================
# HOME PAGE
# =========================

@app.route('/')
def home():
    return redirect(url_for('login'))


# =========================
# STORE DIRECTORY ---> Week 7 (Search Filter)
# =========================

# Shows every store, with search-by-name and filter-by-service, plus a
# live "X waiting" count and an open/closed badge per store so customers
# don't have to click into every store to see if it's worth queueing.
#======================================================================
# STORE DISCOVERY  (/stores)   ---> Week 7 (Search Filter)
# This is the customer-facing directory: search, filter by service,
# filter by open/closed, sort A-Z/Z-A, plus a live "X waiting" count and
# an OPEN/CLOSED badge per store. Nothing here is cached - every value
# is computed fresh from the database on every single page load, which
# is the whole point: change a row in the DB and this page reflects it
# on the very next refresh, no restart needed.
#======================================================================
@app.route('/stores')
def store_discovery():

    # STEP 1: read the 4 filter params from the URL query string.
    # e.g. /stores?search=laundry&service=Payment&status=open&sort=name_asc
    search_query = request.args.get('search', '')
    service_filter = request.args.get('service', '')

    # Grab the logged in user's name from memory, to show "Welcome, X" in the nav
    current_username = session.get('username')

    conn = get_db_connection()

    # STEP 2: build the SQL dynamically. Starts from "every APPROVED
    # store" and adds AND clauses only for the filters actually in use -
    # so a visit with no query params at all just runs the base query.
    # Only APPROVED stores are ever shown to customers - PENDING/REJECTED
    # proposals stay invisible to the public directory, this is what
    # keeps unapproved businesses from being browsable before admin
    # sign-off. The JOIN + DISTINCT combo is needed because a store can
    # have many services - without DISTINCT, a store with 3 services
    # would appear 3 times in the result.
    sql = '''
        SELECT DISTINCT store.*
        FROM store
        LEFT JOIN service ON service.store_id = store.store_id
        WHERE store.store_status = 'APPROVED'
    '''
    params = []

    if search_query:
        sql += ' AND store.store_name LIKE ?'
        params.append('%' + search_query + '%')

    if service_filter:
        sql += ' AND service.service_name = ?'
        params.append(service_filter)

    stores_raw = conn.execute(sql, params).fetchall()

    # STEP 3: a SEPARATE query just to populate the Service filter
    # dropdown's <option> list - this is independent of stores_raw above,
    # it needs every distinct service name that exists (scoped to
    # approved stores), not just services belonging to stores that
    # survived the search/filter.
    #
    # NOTE (known bug, worth fixing before demo day): there used to be a
    # second, unfiltered "all_services = conn.execute('SELECT DISTINCT
    # service_name FROM service...')" line directly after this one, which
    # silently overwrote this correct result with an unfiltered one -
    # meaning the dropdown was actually showing services from PENDING/
    # REJECTED stores too, contradicting this comment. That dead second
    # query has been removed here; if you see it again (e.g. a teammate's
    # merge reintroduces it), delete it - this query alone is correct.
    all_services = conn.execute(
        '''
        SELECT DISTINCT service.service_name
        FROM service
        JOIN store ON store.store_id = service.store_id
        WHERE store.store_status = 'APPROVED'
        ORDER BY service.service_name
        '''
    ).fetchall()

    # STEP 4: for every store that survived the search/filter, compute
    # two LIVE values that aren't stored anywhere as real columns.
    # sqlite3.Row objects are read-only, so convert each store to a plain
    # dict first, then bolt on the two live/computed fields the template
    # needs. Dict lookups work the same as Row lookups in Jinja
    # (store['x']), so nothing in the template has to change for the
    # fields that already existed.
    stores = []
    for row in stores_raw:
        # dict(row) copies the Row into a normal dict - Rows are read-only
        # (you can't do row['new_key'] = value on one), dicts can.
        store = dict(row)

        # 4a: how many customers are currently WAITING for any service at
        # this store right now (Member 2's queue table, joined through
        # service since queue only stores service_id, not store_id
        # directly - service is what links a queue entry back to a store).
        waiting_count = conn.execute(
            '''
            SELECT COUNT(*) AS c
            FROM queue q
            JOIN service s ON q.service_id = s.service_id
            WHERE s.store_id = ?
            AND q.queue_status = 'WAITING'
            ''',
            (store['store_id'],)
        ).fetchone()['c']

        # 4b: a store counts as "open" if it has at least one open counter
        # (Member 3's counter table). There's no separate per-service open
        # flag in the schema, so this is a store-wide approximation: if
        # ANY counter is open, the whole store shows as OPEN.
        open_counters = conn.execute(
            "SELECT COUNT(*) AS c FROM counter WHERE store_id = ? AND counter_status = 'open'",
            (store['store_id'],)
        ).fetchone()['c']

        store['waiting_count'] = waiting_count
        store['is_open'] = open_counters > 0

        # 4c: rough estimated wait = minutes-per-person (falls back to 5
        # if that column is empty/0) times how many people are actually
        # waiting right now. A simple linear estimate, deliberately not a
        # queueing-theory model - kept simple so it's easy to explain.
        per_person = store['estimated_wait_time'] or 5
        store['estimated_wait'] = waiting_count * per_person

        stores.append(store)

    # STEP 5: open/closed filter - done HERE in Python, not in the SQL
    # above, because is_open is something we only just computed in the
    # loop - there's no real "is_open" column to write a WHERE against.
    status_filter = request.args.get('status', '')
    if status_filter == 'open':
        stores = [s for s in stores if s['is_open']]
    elif status_filter == 'closed':
        stores = [s for s in stores if not s['is_open']]

    # STEP 6: A-Z / Z-A sort - same reason, done in Python on the final
    # list. .lower() makes it case-insensitive so "apple" and "Banana"
    # sort correctly against each other instead of by ASCII case.
    sort = request.args.get('sort', '')
    if sort == 'name_asc':
        stores.sort(key=lambda s: s['store_name'].lower())
    elif sort == 'name_desc':
        stores.sort(key=lambda s: s['store_name'].lower(), reverse=True)

    # STEP 7: hand everything to the template - stores.html loops over
    # `stores` to draw the cards, and uses all_services/service_filter/
    # status_filter/sort to pre-select the right dropdown options so the
    # filter UI reflects whatever's currently applied.
    return render_template(
        'stores.html',
        stores=stores,
        search_query=search_query,
        service_filter=service_filter,
        all_services=all_services,
        status_filter=status_filter,
        sort=sort,
        username=current_username
    )

#======================================================================
# USER REGISTRATION  (/register)
# GET  -> blank form.
# POST -> create the account UNVERIFIED, generate + email a 6-digit OTP,
#         then send them to /verify_email. They physically cannot log in
#         until that code is entered (login() doesn't even check
#         is_verified, but the UX funnels them through verify first via
#         the session flag below).
#======================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        # STEP 1: pull the raw form fields out of request.form. username/
        # password use [] (crashes with a 400 if missing - fine, since
        # the HTML form marks them required). email/role use .get() with
        # a default/fallback since they're optional-ish.
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email', '').strip()

        # Grab the role they picked from the dropdown menu/
        role = request.form.get('role', 'CUSTOMER')

        conn = get_db_connection()

        # STEP 2: uniqueness check BEFORE inserting anything. Username is
        # the natural key we log in with, so two accounts sharing one
        # would make login() ambiguous (its query assumes one match).
        existing_user = conn.execute('SELECT * FROM user WHERE username =?', (username,)).fetchone()

        if existing_user:
            error = "That username is already taken! Choose another one."
            # Early return - nothing below this point runs, so no DB
            # write happens and we never reach the OTP step for a
            # rejected signup.
            return render_template('register.html', error=error)

        # STEP 3: OTP GENERATION.
        # random.randint(100000, 999999) picks a random integer in that
        # inclusive range - always exactly 6 digits (100000 is the
        # smallest 6-digit number, 999999 the largest), so it can never
        # come out as e.g. "4821" (4 digits). Wrapped in str() because:
        #   (a) we store/compare it as text later (user['verification_code']
        #       == code, a string equality check in verify_email()), and
        #   (b) if it were left as an int we couldn't preserve a leading
        #       zero - not an issue here since 100000+ never starts with
        #       0, but str() is the safe/correct habit regardless.
        # random.randint() is NOT cryptographically secure - fine for an
        # OTP you're also rate-limiting/expiring via normal app flow, but
        # this is why reset_password() below uses `secrets` instead for
        # its token (a guessable password-reset link is a much bigger
        # risk than a guessable 6-digit code sent to a private inbox).
        code = str(random.randint(100000, 999999))

        # STEP 4: insert the new user row immediately, storing that code
        # in the verification_code column. is_verified is NOT set here -
        # it uses whatever default schema.sql gives it (0 = unverified).
        conn.execute(
            'INSERT INTO user (username, password, role, email, verification_code) VALUES (?, ?, ?, ?, ?)',
            (username, password, role, email, code)
        )
        conn.commit()

        # STEP 5: try to email that code via the shared helper (defined
        # near the top of the file, also reused by resend_code()). If
        # sending fails - bad SMTP creds, no internet, Gmail rejecting
        # the login - send_verification_email() catches the exception
        # internally and returns False rather than raising, so this line
        # does NOT crash registration even when the email never goes out.
        # The user can still reach /verify_email and use "Resend code"
        # once mail is working.
        send_verification_email(email, code)

        # STEP 6: remember WHO we're waiting to verify. Stored in the
        # session (server-trusted, signed cookie) rather than passed as
        # a URL parameter like /verify_email?user=X - if it were a URL
        # param, anyone could type a different username into that URL
        # and start guessing codes for someone else's half-finished
        # signup. Session-based means only the browser that just
        # registered can see/use verify_email for that specific account.
        session['pending_verify'] = username
        return redirect(url_for('verify_email'))

    return render_template('register.html', error=error)


#======================================================================
# USER LOGIN  (/login)
# STEP 1: check username+password match one row.
# STEP 2: start the session.
# STEP 3: branch to a different landing page by role.
#
# NOTE for interview: password is compared as plain text here
# (WHERE password = ?), not hashed. If asked "is this secure?" - no,
# a real version would use werkzeug.security.generate_password_hash /
# check_password_hash. Worth saying this upfront rather than being
# caught not knowing it.
#======================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()

        # One query does both the "does this user exist" and "is the
        # password right" check at once - if either is wrong, user comes
        # back as None (no row matches), and we can't tell from this
        # query alone WHICH one was wrong. That's deliberate: the error
        # message below says "Incorrect username or password" rather
        # than specifying which, so an attacker can't use the error to
        # confirm whether a given username exists in the system.
        user = conn.execute(
            '''
            SELECT *
            FROM user
            WHERE username = ?
            AND password = ?
            ''',
            (username, password)
        ).fetchone()

        if user:
            # This is literally what "being logged in" means in this app -
            # every other protected route just checks session.get(...).
            # No separate "session" table/token in the DB; Flask signs
            # this cookie so the browser can't tamper with it undetected.
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']

            if user['role'] == 'ADMIN':
                return redirect(url_for('admin_dashboard'))

            elif user['role'] == 'STAFF':

                 conn = get_db_connection()

                 store = conn.execute(
                   """
                   SELECT *
                   FROM store
                   WHERE owner_id = ?
                   ORDER BY store_id DESC
                   LIMIT 1
                   """,
                   (user['user_id'],)
                ).fetchone()

                # STAFF has never submitted a store proposal
                 if not store:
                     return redirect(url_for('register_store'))

                # Proposal is still waiting for ADMIN
                 if store['store_status'] == 'PENDING':
                     return redirect(url_for('staff_status'))

                # ADMIN rejected the proposal
                 if store['store_status'] == 'REJECTED':
                     return redirect(url_for('staff_status'))

                # ADMIN approved the proposal
                 if store['store_status'] == 'APPROVED':
                     return redirect(
                         url_for(
                             'staff_dashboard',
                             store_id=store['store_id']
                         )
               )

            else:
                return redirect(url_for('store_discovery'))
        else:
            return render_template(
                'login.html',
                error='Incorrect username or password. Please try again!'
            )

    return render_template('login.html')

#======================================================================
# OTP VERIFICATION  (/verify_email)
# The page the user lands on right after registering. Compares whatever
# code they type against what's stored in the DB for their account.
#======================================================================
@app.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    # STEP 1: who are we verifying? Read from the session, NOT from a URL
    # param or form field - this is the value register() set right
    # before redirecting here. If it's missing, there's no verification
    # in progress for this browser (e.g. someone bookmarked this URL, or
    # came back days later after the session expired) - send them to
    # login instead of showing a broken/empty verify form.
    username = session.get('pending_verify')
    if not username:
        return redirect(url_for('login'))

    error = None
    if request.method == 'POST':
        # STEP 2: grab what they typed and strip whitespace (in case
        # they pasted the code with a leading/trailing space/newline).
        code = request.form.get('code', '').strip()
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()

        # STEP 3: the actual check - does the typed code match the
        # verification_code column for this exact username? Both sides
        # are strings (code is a stripped form string; verification_code
        # was stored as str(random.randint(...)) back in register()), so
        # this is a plain string equality comparison, not numeric.
        if user and user['verification_code'] == code:
            # STEP 4: success - flip is_verified to 1 (TRUE) AND set
            # verification_code to NULL in the same UPDATE. Clearing the
            # code is what makes it single-use: even if someone else
            # somehow learned this code after the fact, re-submitting it
            # won't match anymore because the column is now NULL, not
            # the old 6 digits.
            conn.execute('UPDATE user SET is_verified = 1, verification_code = NULL WHERE username = ?', (username,))
            conn.commit()
            # Done verifying - clear the session flag so this page isn't
            # still "active" for this browser, then send them to log in
            # with their now-verified account.
            session.pop('pending_verify', None)
            return redirect(url_for('login'))

        # STEP 5: wrong code (or, extremely unlikely, no matching user
        # row at all) - show a generic "Incorrect code" error and
        # re-render the SAME page. Session's pending_verify is left
        # alone on purpose, so they can just try typing it again without
        # needing to re-register.
        error = "Incorrect code."

    return render_template('verify_email.html', error=error, username=username)


#======================================================================
# RESEND OTP  (/resend_code, POST only)
# Hit by the "Resend code" button on the verify page - lets someone get
# a fresh code without having to re-register from scratch (e.g. the
# first email never arrived, or they waited too long and want a clean
# code rather than guessing if the old one still works).
#======================================================================
@app.route('/resend_code', methods=['POST'])
def resend_code():
    # STEP 1: same session guard as verify_email() - no pending_verify,
    # no business being on this page, bounce to login.
    username = session.get('pending_verify')
    if not username:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()

    # STEP 2: defensive check - if the account somehow doesn't exist
    # anymore (shouldn't normally happen, but e.g. if it were deleted
    # between registering and clicking resend), don't crash on a None
    # user below, just send them back to login.
    if not user:
        return redirect(url_for('login'))

    # STEP 3: generate a BRAND NEW code the exact same way register()
    # did, and overwrite the old one in the DB. This immediately
    # invalidates the previous code - there's only ever one valid code
    # per account at a time, so clicking resend can't leave two
    # different "correct" codes both accepted.
    new_code = str(random.randint(100000, 999999))
    conn.execute('UPDATE user SET verification_code = ? WHERE username = ?', (new_code, username))
    conn.commit()

    # STEP 4: send it via the SAME shared helper register() uses (DRY -
    # one place to fix if the mail-sending logic ever needs changing).
    # Capture the True/False it returns so we can be honest with the
    # user about whether the email actually went out, instead of always
    # showing "sent!" even when SMTP silently failed.
    sent = send_verification_email(user['email'], new_code)
    notice = "A new code has been sent to your email." if sent else \
        "Couldn't send the email right now, please try again in a moment."

    # STEP 5: re-render the verify page (not redirect) so the notice
    # message shows immediately without an extra page load, and
    # username/pending_verify state is untouched - they're still mid
    # verification, just with a new code now live in the DB.
    return render_template('verify_email.html', error=None, notice=notice, username=username)

#======================================================================
# FORGOT PASSWORD  (/forgot_password)
# Customer types their email, gets a one-time reset LINK (not a 6-digit
# code like the OTP flow - a link is more appropriate here since it can
# carry a long, unguessable token instead of something a human re-types).
#======================================================================
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM user WHERE email = ?', (email,)).fetchone()

        # STEP 1: only do anything if that email actually belongs to an
        # account. Deliberately wrapped so that whether or not `user` is
        # found, the SAME message gets shown at the end (see STEP 4) -
        # this stops someone using this form to check which emails are
        # registered users (a real security pattern called "user
        # enumeration prevention": if a wrong email got a different
        # message than a right one, that difference alone leaks whether
        # an account exists for that address).
        if user:
            # STEP 2: generate the reset token. secrets.token_urlsafe(32)
            # is used here instead of random.randint() like the OTP -
            # deliberately different, because this token IS the entire
            # credential (whoever has the link can reset the password),
            # so it needs to be cryptographically unguessable. `secrets`
            # is Python's module specifically meant for security-
            # sensitive random values; `random` (used for the OTP) is
            # not safe for this purpose. 32 bytes URL-safe encoded is a
            # long, effectively unbrute-forceable string.
            token = secrets.token_urlsafe(32)
            # Expiry timestamp: now + 30 minutes. Stored alongside the
            # token so reset_password() can reject it once stale, even
            # if the token itself is still technically correct.
            expiry = datetime.now() + timedelta(minutes=30)

            conn.execute(
                'UPDATE user SET reset_token = ?, reset_token_expire = ? WHERE user_id = ?',
                (token, expiry, user['user_id'])
            )
            conn.commit()

            # STEP 3: build the actual clickable URL. _external=True is
            # important - without it, url_for() produces a relative path
            # like "/reset_password/abc123", which is meaningless inside
            # an email (there's no "current page" to be relative to); it
            # needs to be a full "http://..." link to work when clicked
            # from an inbox.
            reset_link = url_for('reset_password', token=token, _external=True)

            # Same try/except pattern as elsewhere: a failed send
            # shouldn't crash this request, it just means the email
            # silently didn't arrive (logged to the console via print).
            try:
                msg = Message('Reset your Queues password', recipients=[email])
                msg.body = f'Click here to reset your password: {reset_link}\nThis link expires in 30 minutes.'
                mail.send(msg)
            except Exception as e:
                print(f"Failed to send reset email: {e}")

        # STEP 4: this exact message is shown whether or not `user` was
        # found above - see the enumeration-prevention note in STEP 1.
        message = "If that email is registered, a reset link has been sent."

    return render_template('forgot_password.html', message=message)


#======================================================================
# RESET PASSWORD  (/reset_password/<token>)
# The page the reset link from forgot_password() actually points at.
# The token itself IS the identifier here - notice there's no session
# check and no login required; possessing the right token in the URL is
# what proves "this is really the account owner" (because only their
# inbox received it).
#======================================================================
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db_connection()
    # STEP 1: look the user up BY the token, not by any session/login
    # info - the token in the URL is the only thing identifying who's
    # resetting what.
    user = conn.execute('SELECT * FROM user WHERE reset_token = ?', (token,)).fetchone()

    # STEP 2: no row matched this token at all - either it's a fake/
    # mistyped URL, or (see STEP 4 below) a token that already got used
    # once and cleared to NULL. Fails closed with a plain error rather
    # than silently redirecting anywhere.
    if not user:
        return "Invalid or expired reset link."

    # STEP 3: even with a valid token, check it hasn't expired. The
    # expiry was stored as a timestamp 30 minutes after it was created
    # (forgot_password() STEP 2); fromisoformat() parses that stored
    # string back into a real datetime object so it can be compared
    # against datetime.now().
    expiry = datetime.fromisoformat(user['reset_token_expire'])
    if datetime.now() > expiry:
        conn.close()
        return "This reset link has expired. Please request a new one."

    error = None
    if request.method == 'POST':
        # STEP 4: set the new password, AND null out both reset_token
        # and reset_token_expire in the same UPDATE. Clearing the token
        # is what makes the link single-use - if someone tried
        # reloading/reusing the same reset link a second time after
        # this, STEP 1's lookup would find no row (token is now NULL,
        # and NULL never equals the token string being searched for),
        # so they'd correctly hit "Invalid or expired reset link."
        new_password = request.form['password']

        conn.execute(
            'UPDATE user SET password = ?, reset_token = NULL, reset_token_expire = NULL WHERE user_id = ?',
            (new_password, user['user_id'])
        )
        conn.commit()
        return redirect(url_for('login'))

    # GET request (clicked the link but haven't submitted a new password
    # yet) - show the form, with the token embedded so the POST above
    # knows which reset this submission belongs to.
    return render_template('reset_password.html', error=error, token=token)


@app.route('/my-store')
def my_store():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    stores = conn.execute(
        'SELECT * FROM store WHERE owner_id = ?', (session['user_id'],)
    ).fetchall()

    return render_template('my_store.html', stores=stores, username=session.get('username'))

# Store registration ----> Week 4: Adding form
@app.route('/register_store', methods=['GET', 'POST'])
def register_store():
    if session.get('role') != 'STAFF':
        return redirect(url_for('login'))
    conn = get_db_connection()

    existing_store = conn.execute(
        """
        SELECT * FROM store WHERE owner_id = ?
        ORDER BY store_id DESC LIMIT 1
        """,
        (session['user_id'],)
    ).fetchone()

    if existing_store:
        return redirect(url_for('staff_status'))

    if request.method == 'POST':
        store_name = request.form['name']
        hours = request.form['hours']
        description = request.form.get('description', '')
        wait_time = request.form.get('estimated_wait_time', 5)

        conn.execute(
            """
            INSERT INTO store
            (store_name, operating_hours, store_status, owner_id, store_description, estimated_wait_time)
            VALUES (?, ?, 'PENDING', ?, ?, ?)
            """,
            (store_name, hours, session['user_id'], description, wait_time)
        )
        conn.commit()

        return redirect(url_for('staff_status'))

    return render_template('register_store.html')

# Edit Store Proposal 
@app.route('/edit-store/<int:store_id>', methods=['GET', 'POST'])
def edit_store(store_id):

    if session.get('role') != 'STAFF':
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Get the store belonging to the logged-in staff
    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE store_id = ?
        AND owner_id = ?
        """,
        (store_id, session['user_id'])
    ).fetchone()

    if not store:
        return "Store not found or you do not have access.", 403

    # Only rejected proposals can be edited
    if store['store_status'] != 'REJECTED':
        return redirect(url_for('staff_status'))

    if request.method == 'POST':

        store_name = request.form['name']
        hours = request.form['hours']
        description = request.form.get('description', '')

        # Update proposal and send it back to PENDING
        conn.execute(
            """
            UPDATE store
            SET store_name = ?,
                operating_hours = ?,
                store_description = ?,
                store_status = 'PENDING',
                rejection_reason = NULL
            WHERE store_id = ?
            AND owner_id = ?
            """,
            (
                store_name,
                hours,
                description,
                store_id,
                session['user_id']
            )
        )

        conn.commit()

        return redirect(url_for('staff_status'))

    return render_template(
        'edit_store.html',
        store=store
    )

@app.route('/staff/status')
def staff_status():

    if session.get('role') != 'STAFF':
        return redirect(url_for('login'))

    conn = get_db_connection()

    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE owner_id = ?
        ORDER BY store_id DESC
        LIMIT 1
        """,
        (session['user_id'],)
    ).fetchone()


    return render_template(
        'staff_status.html',
        store=store
    )

# Store Details Page ---> Week 3 & Week 7 (Live queue)

@app.route('/store/<int:store_id>')
def store_details(store_id):
    # Check if the user has a session, if not, redirect to login
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Grab the specific store record based on the clicked store id.
    store = conn.execute('SELECT * FROM store WHERE store_id =?', (store_id,)).fetchone()

    # Fall back error response if someone manually type a fake store ID in the URL
    if not store or store['store_status'] != 'APPROVED':
        return "Store not found", 404

    # Grab all active services linked to this store from Member 3's service table
    services = conn.execute('SELECT * FROM service WHERE store_id = ?', (store_id,)).fetchall()

    # Walk-in vs appointment queues are told apart by the queue_number
    # prefix Member 2 already generates: 'W-xxx' for walk-ins
    # (walk_in_queue()) and 'A-xxx' for appointments that have checked in
    # (check_in_appointment()). No new column needed - just filter on that.
    walkin_waiting = conn.execute(
        '''
        SELECT COUNT(*) AS c
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        AND q.queue_number LIKE 'W-%'
        ''',
        (store_id,)
    ).fetchone()['c']

    appt_waiting = conn.execute(
        '''
        SELECT COUNT(*) AS c
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        AND q.queue_number LIKE 'A-%'
        ''',
        (store_id,)
    ).fetchone()['c']

    open_counters = conn.execute(
        "SELECT COUNT(*) AS c FROM counter WHERE store_id = ? AND counter_status = 'open'",
        (store_id,)
    ).fetchone()['c']

    # Does the logged-in customer currently have a live queue entry (either
    # WAITING or already being SERVING) at THIS store? Pick the most recent
    # one if somehow there's more than one.
    my_queue_row = conn.execute(
        '''
        SELECT q.*
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.user_id = ?
        AND q.queue_status IN ('WAITING', 'SERVING')
        ORDER BY q.queue_id DESC
        LIMIT 1
        ''',
        (store_id, session['user_id'])
    ).fetchone()

    my_queue = None
    if my_queue_row:
        my_queue = dict(my_queue_row)
        # 'W-' / 'A-' prefix tells us which queue type this entry belongs to.
        my_queue['queue_type'] = 'Walk-in' if my_queue['queue_number'].startswith('W-') else 'Appointment'

        # Same "people ahead of me" maths as Member 2's /api/queues/my-status:
        # count everyone still WAITING in this exact service's queue who
        # joined (got a lower queue_id) before I did. 0 ahead once I'm
        # already SERVING.
        if my_queue['queue_status'] == 'WAITING':
            my_queue['people_ahead'] = conn.execute(
                '''
                SELECT COUNT(*) AS c
                FROM queue
                WHERE service_id = ?
                AND queue_status = 'WAITING'
                AND queue_id < ?
                ''',
                (my_queue['service_id'], my_queue['queue_id'])
            ).fetchone()['c']
        else:
            my_queue['people_ahead'] = 0

    # Render the template and pass along the user's session name
    return render_template(
        'store_details.html',
        store=store,
        services=services,
        walkin_waiting=walkin_waiting,
        appt_waiting=appt_waiting,
        is_open=open_counters > 0,
        my_queue=my_queue,
        username=session.get('username')
    )

# Customer Profile (view/edit own account) ---> Week 7

# GET  -> show the logged-in user's own username/email.
# POST -> let them update their email and/or set a new password.
# Deliberately does NOT touch username or role - those aren't meant to
# change after signup, and role changes are an admin concern, not a
# customer self-service one.
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM user WHERE user_id = ?', (session['user_id'],)).fetchone()

    error = None
    success = None

    if request.method == 'POST':
        new_email = request.form.get('email', '').strip()
        new_password = request.form.get('password', '').strip()

        # Password field is optional - only touch it if they actually typed
        # something, so leaving it blank just keeps the current password.
        if new_password:
            conn.execute(
                'UPDATE user SET email = ?, password = ? WHERE user_id = ?',
                (new_email, new_password, session['user_id'])
            )
        else:
            conn.execute(
                'UPDATE user SET email = ? WHERE user_id = ?',
                (new_email, session['user_id'])
            )
        conn.commit()

        # Re-fetch so the page shows the values that actually got saved.
        user = conn.execute('SELECT * FROM user WHERE user_id = ?', (session['user_id'],)).fetchone()
        success = "Profile updated successfully."

    return render_template('profile.html', user=user, error=error, success=success)

# User Logout ---> Week 3
@app.route('/logout')
def logout():
        # Clear the session memory
        session.clear()
        # Redirect user back to login
        return redirect(url_for('login'))


#======================================================================
# -- Member 2(Eugene): Appointment & Queue Api
#======================================================================
@socketio.on('join_store_room')
def on_join_store_room(data):
    store_id = data.get('store_id')
    if store_id:
        room = f"store_{store_id}"
        join_room(room)
        print(f"User joined {room}")

# POST /api/appointments
@app.route('/api/appointments', methods=['POST'])
def create_appointment():
    data = request.get_json(silent=True) or {}

    required = ['user_id', 'service_id', 'appt_datetime']
    if not all(data.get(key) for key in required):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()    
    try:
        user = conn.execute('SELECT 1 FROM user WHERE user_id = ?', (data['user_id'],)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        service = conn.execute('SELECT 1 FROM service WHERE service_id = ?', (data['service_id'],)).fetchone()
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO appointment (user_id, service_id, appt_datetime, appt_status) VALUES (?, ?, ?, 'BOOKED')",
                (data['user_id'], data['service_id'], data['appt_datetime'])
            )
            appt_id = cursor.lastrowid

        create_notification(
            data['user_id'],
            "Your appoinment has been booked successfully."
        )

        return jsonify({'message': 'Appointment created successfully!', 'appointment_id': appt_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# POST /api/queues/walk-in
@app.route('/api/queues/walk-in', methods=['POST'])
def walk_in_queue():
    data = request.get_json(silent=True) or {}
    if not data.get('user_id') or not data.get('service_id'):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db_connection()
    try:
        user = conn.execute('SELECT 1 FROM user WHERE user_id = ?', (data['user_id'],)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        service = conn.execute('SELECT store_id FROM service WHERE service_id = ?', (data['service_id'],)).fetchone()
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        store_id = service['store_id']

        conn.execute("BEGIN IMMEDIATE")
        with conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT q.queue_number
                FROM queue q
                JOIN service s ON q.service_id = s.service_id
                WHERE s.store_id = ? AND q.queue_number LIKE 'W-%'
                ORDER BY q.queue_id DESC LIMIT 1
            """, (store_id,))
            last_record = cursor.fetchone()
            next_num = int(last_record['queue_number'].split('-')[1]) + 1 if last_record else 1
            queue_number = f"W-{next_num:03d}"

            cursor.execute(
                "INSERT INTO queue (user_id, service_id, counter_id, queue_number, queue_status) VALUES (?, ?, NULL, ?, 'WAITING')",
                (data['user_id'], data['service_id'], queue_number)
            )
            queue_id = cursor.lastrowid

            create_notification(
                data['user_id'],
                f"You have successfully joined the queue. Your queue number is {queue_number}."
            )

        socketio.emit('queue_status_updated', {'queue_id': queue_id}, to=f"store_{store_id}")

        return jsonify({'message': 'Successfully joined the walk-in queue!', 'queue_id': queue_id, 'queue_number': queue_number}),201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# PUT /api/appointments/<appt_id>/check-in
@app.route('/api/appointments/<int:appt_id>/check-in', methods=['PUT'])
def check_in_appointment(appt_id):
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        with conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM appointment WHERE appt_id = ?", (appt_id,))
            appt = cursor.fetchone()

            if not appt:
                return jsonify({'error': 'Appointment not found'}), 404
            if appt['appt_status'] != 'BOOKED':
                return jsonify({'error': 'Appointment cannot be checked in'}), 400

            service = cursor.execute("SELECT store_id FROM service WHERE service_id = ?", (appt['service_id'],)).fetchone()

            if not service:
                return jsonify({'error': 'Service linked to this appointment no longer exists'}), 400
            
            store_id = service['store_id']

            cursor.execute("""
                SELECT q.queue_number
                FROM queue q
                JOIN service s ON q.service_id = s.service_id
                WHERE s.store_id = ? AND q.queue_number LIKE 'A-%'
                ORDER BY q.queue_id DESC LIMIT 1
            """, (store_id,))
            last_record = cursor.fetchone()
            next_num = int(last_record['queue_number'].split('-')[1]) + 1 if last_record else 1
            queue_number = f"A-{next_num:03d}"

            cursor.execute("UPDATE appointment SET appt_status = 'CHECKED_IN' WHERE appt_id = ?", (appt_id,))
            cursor.execute(
                "INSERT INTO queue (user_id, service_id, counter_id, queue_number, queue_status) VALUES (?, ?, NULL, ?, 'WAITING')",
                (appt['user_id'], appt['service_id'], queue_number)
            )
            queue_id = cursor.lastrowid

        socketio.emit('queue_status_updated', {'queue_id': queue_id}, to=f"store_{store_id}")

        return jsonify({'message': 'Appointment checked in successfully!', 'queue_id': queue_id, 'queue_number': queue_number}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GET /api/queues/my-status
@app.route('/api/queues/my-status', methods=['GET'])
def get_my_queue_status():
    queue_id = request.args.get('queue_id', type=int)
    if not queue_id:
        return jsonify({'error': 'Missing queue_id parameter'}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.queue_status, q.queue_number, q.service_id, q.counter_id, c.counter_name, s.store_id, s.service_name, st.store_name, st.estimated_wait_time
            FROM queue q
            LEFT JOIN counter c ON q.counter_id = c.counter_id
            JOIN service s ON q.service_id = s.service_id
            JOIN store st ON s.store_id = st.store_id
            WHERE q.queue_id = ?
        """, (queue_id,))
        my_queue = cursor.fetchone()

        if not my_queue:
            return jsonify({'error': 'Queue not found'}), 404

        status = my_queue['queue_status']
        queue_number = my_queue['queue_number']

        # If no counter has been assigned yet
        counter_name = my_queue['counter_name'] or '-'

        if status != 'WAITING':
            return jsonify({
                'queue_number': queue_number,
                'status': status,
                'counter_name': counter_name,
                'people_ahead': 0,
                'wait_time': 0,
                'store_id': my_queue['store_id'],
                'store_name': my_queue['store_name'],
                'service_name': my_queue['service_name']
            }), 200

        cursor.execute(
            "SELECT COUNT(*) AS people_ahead FROM queue WHERE service_id = ? AND queue_status = 'WAITING' AND queue_id < ?",
            (my_queue['service_id'], queue_id)
        )
        people_ahead = cursor.fetchone()['people_ahead']
        db_time = my_queue['estimated_wait_time']
        per_person_time = db_time if db_time else 5
        wait_time = (people_ahead + 1) * per_person_time

        return jsonify({
            'queue_number': queue_number,
            'status': status,
            'counter_name': counter_name,
            'people_ahead': people_ahead,
            'wait_time': wait_time,
            'store_id': my_queue['store_id'],
            'store_name': my_queue['store_name'],
            'service_name': my_queue['service_name']
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GET /api/notifications
@app.route('/api/notifications', methods=['GET'])
def get_notification():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'Missing user_id parameter'}), 400

    conn = get_db_connection()
    try:
        notifications = conn.execute(
            """
            SELECT notification_id, message, is_read
            FROM notification
            WHERE user_id = ?
            ORDER BY notification_id DESC
            """,
            (user_id,)
        ).fetchall()

        return jsonify([
            {
                'notification_id': notification['notification_id'],
                'message': notification['message'],
                'is_read': notification['is_read']
            }
            for notification in notifications
        ]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Page Routes
@app.route('/booking')
def booking_page():
    return render_template('booking.html')

@app.route('/check-in')
def check_in_page():
    return render_template('check_in.html')

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

# Test Session Route for Development Purposes
@app.route('/set-test-session/<int:user_id>')
def set_test_session(user_id):
    session['user_id'] = user_id
    session['username'] = f'testuser_{user_id}'
    return f"Test session set! You are now logged in as User ID: {user_id}"


#======================================================================
# -- Member 3: Store, Service & Counter API
#======================================================================

# =========================
# SERVICE CRUD API
# =========================

# CREATE - Add a new service
@app.route('/api/services', methods=['POST'])
def create_service():
    if session.get('role') != 'STAFF':
        return jsonify({'error': 'Staff access required'}), 403

    data = request.get_json()
    store_id = data.get('store_id')
    service_name = data.get('service_name')

    if not store_id or not service_name:
        return jsonify({'error': 'store_id and service_name are required'}), 400

    conn = get_db_connection()

    store = conn.execute(
        'SELECT * FROM store WHERE store_id = ? AND owner_id = ?',
        (store_id, session['user_id'])
    ).fetchone()

    if not store:
        return jsonify({'error': 'You do not have access to this store'}), 403

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO service (store_id, service_name) VALUES (?, ?)",
        (store_id, service_name)
    )
    conn.commit()
    service_id = cursor.lastrowid

    return jsonify({'message': 'Service created successfully', 'service_id': service_id}), 201


# READ - Get all services for a store
@app.route('/api/services/<int:store_id>', methods=['GET'])
def get_services(store_id):
    conn = get_db_connection()

    services = conn.execute(
        """
        SELECT *
        FROM service
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in services
    ]), 200


# UPDATE - Update a service
@app.route('/api/services/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    data = request.get_json()

    service_name = data.get('service_name')

    if not service_name:
        return jsonify({
            'error': 'service_name is required'
        }), 400

    conn = get_db_connection()

    # Check whether service exists
    service = conn.execute(
        'SELECT * FROM service WHERE service_id = ?',
        (service_id,)
    ).fetchone()

    if not service:
        return jsonify({
            'error': 'Service not found'
        }), 404

    # Update service
    conn.execute(
        """
        UPDATE service
        SET service_name = ?
        WHERE service_id = ?
        """,
        (service_name, service_id)
    )

    conn.commit()

    return jsonify({
        'message': 'Service updated successfully'
    }), 200


# DELETE - Delete a service
@app.route('/api/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    conn = get_db_connection()

    # Check whether service exists
    service = conn.execute(
        'SELECT * FROM service WHERE service_id = ?',
        (service_id,)
    ).fetchone()

    if not service:
        return jsonify({
            'error': 'Service not found'
        }), 404

    # Delete service
    conn.execute(
        'DELETE FROM service WHERE service_id = ?',
        (service_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Service deleted successfully'
    }), 200

# =========================
# COUNTER CRUD API
# =========================

# CREATE - Add a new counter
@app.route('/api/counters', methods=['POST'])
def create_counter():
    if session.get('role') != 'STAFF':
        return jsonify({'error': 'Staff access required'}), 403

    data = request.get_json()
    store_id = data.get('store_id')
    counter_name = data.get('counter_name')

    if not store_id or not counter_name:
        return jsonify({'error': 'store_id and counter_name are required'}), 400

    conn = get_db_connection()

    store = conn.execute(
        'SELECT * FROM store WHERE store_id = ? AND owner_id = ?',
        (store_id, session['user_id'])
    ).fetchone()

    if not store:
        return jsonify({'error': 'You do not have access to this store'}), 403

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO counter (store_id, counter_name) VALUES (?, ?)",
        (store_id, counter_name)
    )
    conn.commit()
    counter_id = cursor.lastrowid

    return jsonify({'message': 'Counter created successfully', 'counter_id': counter_id}), 201


# READ - Get all counters for a store
@app.route('/api/counters/<int:store_id>', methods=['GET'])
def get_counters(store_id):
    conn = get_db_connection()

    counters = conn.execute(
        """
        SELECT * FROM counter
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in counters
    ]), 200


# UPDATE - Edit counter name and status
@app.route('/api/counters/<int:counter_id>', methods=['PUT'])
def update_counter(counter_id):
    data = request.get_json()

    counter_name = data.get('counter_name')
    counter_status = data.get('counter_status')

    if not counter_name or not counter_status:
        return jsonify({
            'error': 'counter_name and counter_status are required'
        }), 400

    conn = get_db_connection()

    counter = conn.execute(
        'SELECT * FROM counter WHERE counter_id = ?',
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    conn.execute(
        """
        UPDATE counter
        SET counter_name = ?,
            counter_status = ?
        WHERE counter_id = ?
        """,
        (counter_name, counter_status, counter_id)
    )

    conn.commit()

    return jsonify({
        'message': 'Counter updated successfully'
    }), 200


# DELETE - Remove a counter
@app.route('/api/counters/<int:counter_id>', methods=['DELETE'])
def delete_counter(counter_id):

    conn = get_db_connection()

    counter = conn.execute(
        'SELECT * FROM counter WHERE counter_id = ?',
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    conn.execute(
        'DELETE FROM counter WHERE counter_id = ?',
        (counter_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Counter deleted successfully'
    }), 200

# =========================
# COUNTER OPEN / CLOSE
# =========================

@app.route('/api/counters/<int:counter_id>/status', methods=['PATCH'])
def update_counter_status(counter_id):
    data = request.get_json()

    counter_status = data.get('counter_status')

    # Only allow open or closed
    if counter_status not in ['open', 'closed']:
        return jsonify({
            'error': 'counter_status must be open or closed'
        }), 400

    conn = get_db_connection()

    # Check whether counter exists
    counter = conn.execute(
        'SELECT * FROM counter WHERE counter_id = ?',
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Update counter status
    conn.execute(
        """
        UPDATE counter
        SET counter_status = ?
        WHERE counter_id = ?
        """,
        (counter_status, counter_id)
    )

    conn.commit()

    return jsonify({
        'message': f'Counter status updated to {counter_status}',
        'counter_id': counter_id,
        'counter_status': counter_status
    }), 200

#----------------------------------------------------------------------
# Store CRUD API
#----------------------------------------------------------------------

# READ - Get all stores
@app.route('/api/stores', methods=['GET'])
def get_stores():
    conn = get_db_connection()

    stores = conn.execute(
        'SELECT * FROM store'
    ).fetchall()


    return jsonify([dict(row) for row in stores]), 200

# CREATE - Add a new store
@app.route('/api/stores', methods=['POST'])
def create_store():
    data = request.get_json()

    store_name = data.get('store_name')
    store_status = data.get('store_status', 'PENDING')
    operating_hours = data.get('operating_hours')
    estimated_wait_time = data.get('estimated_wait_time', 0)

    if not store_name:
        return jsonify({
            'error': 'store_name is required'
        }), 400

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO store
        (store_name, store_status, operating_hours, estimated_wait_time)
        VALUES (?, ?, ?, ?)
        """,
        (
            store_name,
            store_status,
            operating_hours,
            estimated_wait_time
        )
    )

    conn.commit()

    store_id = cursor.lastrowid


    return jsonify({
        'message': 'Store created successfully',
        'store_id': store_id
    }), 201

# UPDATE - Update an existing store
@app.route('/api/stores/<int:store_id>', methods=['PUT'])
def update_store(store_id):
    data = request.get_json()

    store_name = data.get('store_name')
    store_status = data.get('store_status')
    operating_hours = data.get('operating_hours')
    estimated_wait_time = data.get('estimated_wait_time')

    conn = get_db_connection()

    existing_store = conn.execute(
        'SELECT * FROM store WHERE store_id = ?',
        (store_id,)
    ).fetchone()

    if not existing_store:
        return jsonify({
            'error': 'Store not found'
        }), 404

    conn.execute(
        """
        UPDATE store
        SET store_name = ?,
            store_status = ?,
            operating_hours = ?,
            estimated_wait_time = ?
        WHERE store_id = ?
        """,
        (
            store_name,
            store_status,
            operating_hours,
            estimated_wait_time,
            store_id
        )
    )

    conn.commit()

    return jsonify({
        'message': 'Store updated successfully'
    }), 200

# DELETE - Delete a store
@app.route('/api/stores/<int:store_id>', methods=['DELETE'])
def delete_store(store_id):
    conn = get_db_connection()

    existing_store = conn.execute(
        'SELECT * FROM store WHERE store_id = ?',
        (store_id,)
    ).fetchone()

    if not existing_store:
        return jsonify({
            'error': 'Store not found'
        }), 404

    conn.execute(
        'DELETE FROM store WHERE store_id = ?',
        (store_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Store deleted successfully'
    }), 200

# Store approval or rejection by admin
@app.route('/api/stores/<int:store_id>/status', methods=['PATCH'])
def update_store_status(store_id):
    if session.get('role') != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json() or {}
    new_status = data.get('store_status')
    rejection_reason = data.get('rejection_reason', '').strip()

    if new_status not in ['PENDING', 'APPROVED', 'REJECTED']:
        return jsonify({'error': 'Invalid store status'}), 400

    if new_status == 'REJECTED' and not rejection_reason:
        return jsonify({'error': 'A rejection reason is required'}), 400

    conn = get_db_connection()

    store = conn.execute(
        'SELECT * FROM store WHERE store_id = ?', (store_id,)
    ).fetchone()

    if not store:
        return jsonify({'error': 'Store not found'}), 404

    # Clear any old rejection reason when approving; save the new one when rejecting
    conn.execute(
        """
        UPDATE store
        SET store_status = ?,
            rejection_reason = ?
        WHERE store_id = ?
        """,
        (new_status, rejection_reason if new_status == 'REJECTED' else None, store_id)
    )
    conn.commit()

    # Let the staff member know why, via your existing notification system
    create_notification(
        store['owner_id'],
        f"Your store '{store['store_name']}' was {new_status.lower()}."
        + (f" Reason: {rejection_reason}" if new_status == 'REJECTED' else "")
    )

    return jsonify({
        'message': 'Store status updated successfully',
        'store_id': store_id,
        'store_status': new_status
    }), 200
    
# Pending Stores API
@app.route('/api/stores/pending', methods=['GET'])
def get_pending_stores():

    if session.get('role') != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403

    conn = get_db_connection()

    stores = conn.execute(
        """
        SELECT
            store.store_id,
            store.store_name,
            store.operating_hours,
            store.store_status,
            store.owner_id,
            user.username
        FROM store
        JOIN user
        ON store.owner_id = user.user_id
        WHERE store.store_status = 'PENDING'
        ORDER BY store.store_id DESC
        """
    ).fetchall()


    return jsonify([
        dict(store)
        for store in stores
    ]), 200
    
# =========================
# STAFF QUEUE CONTROL API
# =========================

# CALL NEXT CUSTOMER
@app.route('/api/counters/<int:counter_id>/call-next', methods=['POST'])
def call_next_customer(counter_id):

    conn = get_db_connection()

    # Check whether counter exists
    counter = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE counter_id = ?
        """,
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Check whether counter is open
    if counter['counter_status'] != 'open':
        return jsonify({
            'error': 'Counter is closed'
        }), 400

    # Find the next waiting customer assigned to this counter
    queue = conn.execute(
        """
        SELECT q.*
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        ORDER BY q.queue_id ASC
        LIMIT 1
        """,
        (counter['store_id'],)
    ).fetchone()

    if not queue:
        return jsonify({
            'message': 'No customers waiting'
        }), 404

    # Change queue status to SERVING
    conn.execute(
        """
        UPDATE queue
        SET counter_id = ?,
            queue_status = 'SERVING'
        WHERE queue_id = ?
        """,
        (counter_id, queue['queue_id'])
    )

    conn.commit()

    # Member 2 (Eugene): Notification thorugh email
    user_info = conn.execute(
        """
        SELECT u.email, u.username, c.counter_name, s.store_name
        FROM queue q
        JOIN user u ON q.user_id = u.user_id
        JOIN counter c ON c.counter_id = ?
        JOIN service serv ON q.service_id = serv.service_id
        JOIN store s ON serv.store_id = s.store_id
        WHERE q.queue_id = ?
        """,
        (counter_id, queue['queue_id'])
    ).fetchone()

    if user_info and user_info['email']:
        try:
            msg = Message(
                f"It's your turn at {user_info['store_name']}!",
                recipients=[user_info['email']]
            )
            msg.body = f"Hello {user_info['username']},\n\nIt is now your turn! Please proceed to {user_info['counter_name']} immediately.\n\nThank you for using Queues!"
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send turn notification email: {e}")

    # Get updated queue
    updated_queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue['queue_id'],)
    ).fetchone()

    socketio.emit('queue_status_updated', {'queue_id': queue['queue_id']}, to=f"store_{counter['store_id']}")
    
    return jsonify({
        'message': 'Next customer called successfully',
        'queue': dict(updated_queue)
    }), 200


# SKIP CUSTOMER
@app.route('/api/queues/<int:queue_id>/skip', methods=['PATCH'])
def skip_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Only SERVING customer can be skipped
    if queue['queue_status'] != 'SERVING':
        return jsonify({
            'error': 'Only a serving customer can be skipped'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET queue_status = 'SKIPPED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Customer skipped successfully',
        'queue_id': queue_id,
        'status': 'SKIPPED'
    }), 200


# RECALL CUSTOMER
@app.route('/api/queues/<int:queue_id>/recall', methods=['PATCH'])
def recall_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Customer must currently be SERVING
    if queue['queue_status'] != 'SERVING':
        return jsonify({
            'error': 'Only a serving customer can be recalled'
        }), 400

    return jsonify({
        'message': 'Customer recalled successfully',
        'queue_id': queue_id,
        'queue_number': queue['queue_number'],
        'status': 'SERVING'
    }), 200


# COMPLETE CUSTOMER SERVICE
@app.route('/api/queues/<int:queue_id>/complete', methods=['PATCH'])
def complete_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Only SERVING customer can be completed
    if queue['queue_status'] != 'SERVING':
        return jsonify({
            'error': 'Only a serving customer can be completed'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET queue_status = 'COMPLETED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()

    return jsonify({
        'message': 'Service completed successfully',
        'queue_id': queue_id,
        'status': 'COMPLETED'
    }), 200


# CANCEL QUEUE
@app.route('/api/queues/<int:queue_id>/cancel', methods=['PATCH'])
def cancel_queue(queue_id):

    conn = get_db_connection()

    queue = conn.execute(
        """
        SELECT q.*, s.store_id
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE q.queue_id = ?
        """,
        (queue_id,)
    ).fetchone()

    if not queue:
        return jsonify({
            'error': 'Queue not found'
        }), 404

    # Cannot cancel completed/skipped/cancelled queue
    if queue['queue_status'] in ['COMPLETED', 'SKIPPED', 'CANCELLED']:
        return jsonify({
            'error': 'Queue can no longer be cancelled'
        }), 400

    conn.execute(
        """
        UPDATE queue
        SET queue_status = 'CANCELLED'
        WHERE queue_id = ?
        """,
        (queue_id,)
    )

    conn.commit()
    conn.close()

    socketio.emit('queue_status_updated', {'queue_id': queue_id}, to=f"store_{queue['store_id']}")

    return jsonify({
        'message': 'Queue cancelled successfully',
        'queue_id': queue_id,
        'status': 'CANCELLED'
    }), 200

# =========================
# QUEUE STATUS & HISTORY API
# =========================

# GET - View current queue for a counter
@app.route('/api/counters/<int:counter_id>/queue', methods=['GET'])
def get_counter_queue(counter_id):

    conn = get_db_connection()

    # Check whether counter exists
    counter = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE counter_id = ?
        """,
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Get queues for this counter
    queues = conn.execute(
        """
        SELECT q.*, s.service_name
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE q.counter_id = ?
        AND q.queue_status IN ('WAITING', 'SERVING')
        ORDER BY q.queue_id ASC
        """,
        (counter_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in queues
    ]), 200

# GET - View queue history (optional filters: store_id, date=YYYY-MM-DD)
@app.route('/api/queues/history', methods=['GET'])
def get_queue_history():
    store_id = request.args.get('store_id')
    date = request.args.get('date')
    conn = get_db_connection()

    try:
        sql = """
            SELECT q.*,
                   s.service_name,
                   c.counter_name,
                   datetime(q.created_at, 'localtime') AS created_local
            FROM queue q
            LEFT JOIN service s ON q.service_id = s.service_id
            LEFT JOIN counter c ON q.counter_id = c.counter_id
            WHERE q.queue_status IN ('COMPLETED', 'SKIPPED', 'CANCELLED')
        """
        params = []

        if store_id and store_id != 'ALL':
            sql += " AND s.store_id = ?"
            params.append(store_id)

        if date:
            sql += " AND date(q.created_at, 'localtime') = ?"
            params.append(date)

        sql += " ORDER BY q.queue_id DESC"

        rows = conn.execute(sql, params).fetchall()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        print(f"Error fetching queue history: {e}")
        return jsonify({'error': str(e)}), 500

# GET - View queue status summary
@app.route('/api/counters/<int:counter_id>/queue/status', methods=['GET'])
def get_queue_status(counter_id):

    conn = get_db_connection()

    # Check counter
    counter = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE counter_id = ?
        """,
        (counter_id,)
    ).fetchone()

    if not counter:
        return jsonify({
            'error': 'Counter not found'
        }), 404

    # Find currently serving customer
    serving = conn.execute(
        """
        SELECT *
        FROM queue
        WHERE counter_id = ?
        AND queue_status = 'SERVING'
        ORDER BY queue_id ASC
        LIMIT 1
        """,
        (counter_id,)
    ).fetchone()

    # Count waiting customers
    waiting = conn.execute(
        """
        SELECT COUNT(*) AS waiting_count
        FROM queue
        WHERE counter_id = ?
        AND queue_status = 'WAITING'
        """,
        (counter_id,)
    ).fetchone()


    return jsonify({
        'counter_id': counter_id,
        'serving': dict(serving) if serving else None,
        'waiting_count': waiting['waiting_count']
    }), 200

# GET - View status history for one queue
@app.route('/api/queues/<int:queue_id>/history', methods=['GET'])
def get_queue_status_history(queue_id):

    conn = get_db_connection()

    history = conn.execute(
        """
        SELECT *
        FROM queue_history
        WHERE queue_id = ?
        ORDER BY timestamp ASC
        """,
        (queue_id,)
    ).fetchall()


    return jsonify([
        dict(row) for row in history
    ]), 200

# =========================
# STAFF DASHBOARD API
# =========================

@app.route('/api/staff/dashboard/<int:store_id>', methods=['GET'])
def get_staff_dashboard(store_id):

    conn = get_db_connection()

    # Check whether store exists
    store = conn.execute(
        """
        SELECT *
        FROM store
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchone()

    if not store:
        return jsonify({
            'error': 'Store not found'
        }), 404

    # Get all counters for this store
    counters = conn.execute(
        """
        SELECT *
        FROM counter
        WHERE store_id = ?
        """,
        (store_id,)
    ).fetchall()

    # Count waiting customers
    waiting = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        """,
        (store_id,)
    ).fetchone()
 
        # Waiting walk-ins (queue numbers start with 'W-')
    walk_in = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        AND q.queue_number LIKE 'W-%'
        """,
        (store_id,)
    ).fetchone()

    # Waiting appointments that have checked in (queue numbers start with 'A-')
    appointment = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'WAITING'
        AND q.queue_number LIKE 'A-%'
        """,
        (store_id,)
    ).fetchone()

 # Count currently serving
    serving = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'SERVING'
        """,
        (store_id,)
    ).fetchone()


    # Count completed
    completed = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'COMPLETED'
        """,
        (store_id,)
    ).fetchone()

    # Count skipped
    skipped = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'SKIPPED'
        """,
        (store_id,)
    ).fetchone()

    # Count cancelled
    cancelled = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue q
        JOIN service s ON q.service_id = s.service_id
        WHERE s.store_id = ?
        AND q.queue_status = 'CANCELLED'
        """,
        (store_id,)
    ).fetchone()


    return jsonify({
        'store': dict(store),

        'counters': [
            dict(counter)
            for counter in counters
        ],

        'queue_summary': {
            'waiting': waiting['total'],
            'walk_in': walk_in['total'],
            'appointment': appointment['total'],
            'serving': serving['total'],
            'completed': completed['total'],
            'skipped': skipped['total'],
            'cancelled': cancelled['total']
        }
    }), 200

# =========================
# ADMIN STATISTICS API
# =========================

@app.route('/api/stats/queues', methods=['GET'])
def get_queue_stats():
    if session.get('role') != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403

    period = request.args.get('period', 'day')
    store_id = request.args.get('store_id')   # <-- read it

    period_formats = {
        'day':   '%Y-%m-%d',
        'week':  '%Y-%W',
        'month': '%Y-%m',
        'year':  '%Y'
    }

    if period not in period_formats:
        return jsonify({'error': 'period must be one of: day, week, month, year'}), 400

    fmt = period_formats[period]
    conn = get_db_connection()

    if store_id and store_id != 'ALL':
        rows = conn.execute(
            f"""
            SELECT strftime('{fmt}', q.created_at) AS period_label,
                   COUNT(*) AS total_queues
            FROM queue q
            JOIN service s ON q.service_id = s.service_id
            WHERE s.store_id = ?
            GROUP BY period_label
            ORDER BY period_label DESC
            LIMIT 30
            """,
            (store_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT strftime('{fmt}', created_at) AS period_label,
                   COUNT(*) AS total_queues
            FROM queue
            GROUP BY period_label
            ORDER BY period_label DESC
            LIMIT 30
            """
        ).fetchall()

    return jsonify([dict(row) for row in rows]), 200

@app.route('/api/stats/stores', methods=['GET'])
def get_store_stats():
    if session.get('role') != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403

    period = request.args.get('period', 'month')

    period_formats = {
        'day':   '%Y-%m-%d',
        'week':  '%Y-%W',
        'month': '%Y-%m',
        'year':  '%Y'
    }

    if period not in period_formats:
        return jsonify({'error': 'period must be one of: day, week, month, year'}), 400

    fmt = period_formats[period]

    conn = get_db_connection()

    rows = conn.execute(
        f"""
        SELECT strftime('{fmt}', created_at) AS period_label,
               COUNT(*) AS total_registered
        FROM store
        GROUP BY period_label
        ORDER BY period_label DESC
        LIMIT 30
        """
    ).fetchall()

    return jsonify([dict(row) for row in rows]), 200

if __name__ == '__main__':
    with app.app_context():
        init_db()
        create_admin()

    socketio.run(app, debug=True, port=5000)