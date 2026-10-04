document.addEventListener("DOMContentLoaded", function () {
  // Browser "Back" Button Prevention (History Hijacking)
  // Avoid users from accidentally leaving the queue page by clicking the browser's back button
  history.pushState(null, null, location.href); // Push current page to history stack
  window.addEventListener("popstate", function () {
    history.pushState(null, null, location.href); // Force them back to the current page
    alert(
      "You are currently in a queue. Please use the 'Cancel Queue' button to leave.",
    );
  });

  // URL Parameters & Initialization
  // From URL get the queue_id
  const urlParams = new URLSearchParams(window.location.search);
  const currentQueueId = urlParams.get("queue_id");

  // If no queue_id is found in the URL, redirect to the store list page
  if (!currentQueueId) {
    alert("Queue ID not found! Redirecting to home.");
    window.location.href = "/stores";
    return;
  }

  // Get references to all necessary DOM elements
  const hiddenQueueIdEl = document.getElementById("currentQueueId");
  if (hiddenQueueIdEl) hiddenQueueIdEl.value = currentQueueId;
  const queueNumberEl = document.getElementById("queueNumberDisplay");
  const peopleAheadEl = document.getElementById("peopleAhead");
  const waitTimeEl = document.getElementById("waitTime");
  const queueStatusEl = document.getElementById("queueStatus");
  const backBtn = document.getElementById("backToStoreBtn");
  const cancelBtn = document.getElementById("cancelQueueBtn");
  const counterNameEl = document.getElementById("counterName");
  const hiddenStoreIdEl = document.getElementById("currentStoreId");

  // Initialize Bootstrap's toast component for non-intrusive notifications
  const toastElement = document.getElementById("alertToast");
  let toast;
  if (toastElement) {
    toast = new bootstrap.Toast(toastElement);
  }

  // Helper function to display toast notifications
  function showNotification(message) {
    const toastMsgEl = document.getElementById("toastMessage");
    if (toastMsgEl && toast) {
      toastMsgEl.innerText = message;
      toast.show();
    }
  }

  // Global State Variables
  let hasNotifiedApproaching = false; // Flag to ensure the "almost your turn" toast only triggers once
  const socket = io(); // Initialize Socket.IO client for real-time updates
  let waitEndTime = null; // Absolute timestamp for when the wait is expected to end
  let waitTimer = null; // Reference to the setInterval timer
  let lastPeopleAhead = null; // Track changes to trigger UI updates
  let lastQueueStatus = null; // Track status changes (e.g., WAITING -> SERVING)

  // Client-side Countdown Timer Logic
  function startWaitCountdown(minutes) {
    // Clear any existing timer to avoid multiple intervals running simultaneously
    if (waitTimer) {
      clearInterval(waitTimer);
    }

    // Calculate the exact future timestamp (in milliseconds)
    waitEndTime = Date.now() + Number(minutes || 0) * 60 * 1000;

    function updateWaitTime() {
      // Calculate remaining milliseconds
      const remainingMs = waitEndTime - Date.now();
      // Convert back to minutes, using Math.ceil to round up
      const remainingMinutes = Math.max(0, Math.ceil(remainingMs / 60000));

      if (waitTimeEl) {
        waitTimeEl.innerText = remainingMinutes;
      }

      // Stop the timer if time is up
      if (remainingMs <= 0) {
        clearInterval(waitTimer);
        waitTimer = null;
      }
    }

    // Run once immediately, then interval every 1 second
    updateWaitTime();
    waitTimer = setInterval(updateWaitTime, 1000);
  }

  // Fetch queue data logic
  // Request the actual queue data from the backend API
  function fetchQueueStatus() {
    fetch(`/api/queues/my-status?queue_id=${currentQueueId}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          console.error("Error fetching queue status:", data.error);
          return;
        }

        // Join the specific store's Socket.IO room to receive targeted real-time updates
        if (data.store_id && hiddenStoreIdEl) {
          hiddenStoreIdEl.value = data.store_id;
          if (socket.connected) {
            socket.emit("join_store_room", { store_id: data.store_id });
          }
        }
        // Update basic text UI elements
        if (queueNumberEl) queueNumberEl.innerText = data.queue_number;

        if (data.store_name) {
          const storeNameEl = document.getElementById("storeName");
          if (storeNameEl) storeNameEl.innerText = data.store_name;
        }
        if (data.service_name) {
          const serviceNameEl = document.getElementById("serviceName");
          if (serviceNameEl) serviceNameEl.innerText = data.service_name;
        }

        // Dynamically change badge color based on queue status
        if (queueStatusEl) {
          queueStatusEl.innerText = data.status;
          if (data.status === "WAITING") {
            queueStatusEl.className =
              "badge bg-warning text-dark fs-5 mt-3 mb-4";
          } else if (data.status === "SERVING") {
            queueStatusEl.className =
              "badge bg-primary text-white fs-5 mt-3 mb-4";
          } else {
            queueStatusEl.className =
              "badge bg-secondary text-white fs-5 mt-3 mb-4";
          }
        }
        // Update people ahead
        if (peopleAheadEl) peopleAheadEl.innerText = data.people_ahead ?? 0;
        // Timer Logic: Only run countdown if user is WAITING
        if (data.status === "WAITING") {
          // Restart timer ONLY IF wait time data changed or status just changed to WAITING
          if (
            waitEndTime === null ||
            lastPeopleAhead !== data.people_ahead ||
            lastQueueStatus !== data.status
          ) {
            startWaitCountdown(data.wait_time ?? 0);
          }
        } else {
          // If not waiting, stop the timer and reset the display
          if (waitTimer) {
            clearInterval(waitTimer);
            waitTimer = null;
          }

          waitEndTime = null;

          if (waitTimeEl) {
            waitTimeEl.innerText = 0;
          }
        }
        // Update counter name (where the user should go)
        if (counterNameEl) {
          counterNameEl.innerText = data.counter_name ?? "-";
        }

        // Handle button visibility based on queue status
        const finished = ["COMPLETED", "SKIPPED", "CANCELLED"];
        const isFinished = finished.includes(data.status);

        if (backBtn) {
          backBtn.href = `/store/${data.store_id}`;
          backBtn.style.display = isFinished ? "inline-block" : "none"; // Show "Back to Store" button only if the queue is finished
        }
        if (cancelBtn && isFinished) {
          cancelBtn.style.display = "none"; // Hide "Cancel Queue" button if the queue is finished
        }

        // Trigger notifications based on status changes
        if (lastQueueStatus && lastQueueStatus !== data.status) {
          if (data.status === "SERVING") {
            alert(
              `🎉 It is your turn! Please proceed to ${data.counter_name ?? "the counter"}.`,
            );
            showNotification(
              `It is your turn at ${data.counter_name ?? "the counter"}!`,
            );
          } else if (data.status === "COMPLETED") {
            alert("✅ Your service is completed. Thank you!");
          } else if (data.status === "SKIPPED") {
            alert("⚠️ You have been skipped. Please contact the staff.");
          } else if (data.status === "CANCELLED") {
            alert("❌ Your queue has been cancelled.");
          }
        }

        // Trigger Warm Reminder Notification: Alert when only 2 people are left
        if (data.status === "WAITING") {
          if (
            data.people_ahead <= 2 &&
            data.people_ahead > 0 &&
            !hasNotifiedApproaching // Only notify once when approaching
          ) {
            showNotification(
              "🔔 Warm reminder: It is almost your turn! Please proceed to the service counter.",
            );
            hasNotifiedApproaching = true;
          } else if (data.people_ahead > 2) {
            // Reset flag if queue somehow goes back up
            hasNotifiedApproaching = false;
          }
        }

        // Save current state for next comparison to detect changes
        lastPeopleAhead = data.people_ahead;
        lastQueueStatus = data.status;
      })
      .catch((error) => console.error("Error fetching queue status:", error));
  }

  // Initial fetch on page load
  fetchQueueStatus();

  // WebSocket (Socket.IO) Event Listeners
  socket.on("connect", function () {
    console.log("WebSocket connected successfully!");
    // Rejoin the room for the current store if the page is refreshed or reconnected
    if (hiddenStoreIdEl && hiddenStoreIdEl.value) {
      socket.emit("join_store_room", { store_id: hiddenStoreIdEl.value });
    }
    // Fetch latest status in case events were missed during disconnection
    fetchQueueStatus();
  });

  // When backend emits a queue status update, trigger an API fetch to get exact latest data
  socket.on("queue_status_updated", function (data) {
    console.log("Queue data changed! Fetching new status instantly...");
    fetchQueueStatus();
  });
  socket.on("disconnect", function () {
    console.log("WebSocket disconnected.");
  });

  // Cancel Queue Button
  if (cancelBtn) {
    cancelBtn.addEventListener("click", function () {
      if (confirm("Are you sure you want to cancel your queue?")) {
        // Send a PATCH request to update the queue status to CANCELLED
        fetch(`/api/queues/${currentQueueId}/cancel`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
        })
          .then((response) => response.json())
          .then((data) => {
            if (data.error) {
              alert("Failed to cancel queue: " + data.error);
            } else {
              alert("Queue cancelled successfully!");
              fetchQueueStatus(); // Refresh UI to show cancelled state
            }
          })
          .catch((error) => {
            console.error("Error:", error);
            alert("An error occurred while trying to cancel the queue.");
          });
      }
    });
  }
});
