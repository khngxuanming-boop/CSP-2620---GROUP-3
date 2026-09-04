document.addEventListener("DOMContentLoaded", function () {
  // Initial fake data
  let peopleAhead = 4;
  let waitTime = 20;

  // Get references to the DOM elements
  const peopleAheadEl = document.getElementById("peopleAhead");
  const waitTimeEl = document.getElementById("waitTime");
  const queueStatusEl = document.getElementById("queueStatus");
  const cancelBtn = document.getElementById("cancelQueueBtn");

  // Initialize Bootstrap's toast component
  const toastElement = document.getElementById("alertToast");
  let toast;
  if (toastElement) {
    toast = new bootstrap.Toast(toastElement);
  }

  // Encapsulated function to show notifications
  function showNotification(message) {
    const toastMsgEl = document.getElementById("toastMessage");
    if (toastMsgEl && toast) {
      toastMsgEl.innerText = message;
      toast.show();
    }
  }

  // Mock interval to simulate real-time data updates from the server (every 5 seconds)
  const mockInterval = setInterval(() => {
    if (peopleAhead > 0) {
      // Simulate the queue moving forward
      peopleAhead -= 1;
      waitTime -= 5;

      // Update the numbers on the page
      if (peopleAheadEl) peopleAheadEl.innerText = peopleAhead;
      if (waitTimeEl) waitTimeEl.innerText = waitTime;

      // Trigger notification: Alert when only 2 people are left
      if (peopleAhead === 2) {
        showNotification(
          "🔔 Warm reminder: Only 2 people left ahead of you. Please proceed to the service counter.",
        );
      }

      // When it's your turn (status changes from WAITING to CALLED)
      if (peopleAhead === 0) {
        if (queueStatusEl) {
          queueStatusEl.className =
            "badge bg-success text-white fs-5 mt-3 mb-4";
          queueStatusEl.innerText = "CALLED (please proceed to counter 2)";
        }
        showNotification(
          "🎉 It's your turn! Please proceed to counter 2 immediately.",
        );
        clearInterval(mockInterval); // Stop the timer
      }
    }
  }, 5000);

  // Cancel queue logic
  if (cancelBtn) {
    cancelBtn.addEventListener("click", function () {
      if (
        confirm(
          "Are you sure you want to cancel your current queue? This action cannot be undone.",
        )
      ) {
        alert("Queue cancelled, status changed to CANCELLED.");
        clearInterval(mockInterval); // Stop the timer
        window.location.href = "check_in.html"; // Return to main page
      }
    });
  }
});
