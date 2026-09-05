document.addEventListener("DOMContentLoaded", function () {
  // From URL get the queue_id
  const urlParams = new URLSearchParams(window.location.search);
  const currentQueueId = urlParams.get("queue_id");

  if (!currentQueueId) {
    alert("Queue ID not found! Redirecting to home.");
    window.location.href = "/stores";
    return;
  }

  // Get references to the DOM elements
  const queueNumberEl = document.getElementById("queueNumberDisplay");
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

  // Flag to track if the approaching notification has been shown
  let hasNotifiedApproaching = false;

  // Request the actual queue data from the backend API
  function fetchQueueStatus() {
    fetch(`/api/queues/my-status?queue_id=${currentQueueId}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          console.error("Error fetching queue status:", data.error);
          return;
        }

        // Update the queue number and status on the page
        if (queueNumberEl) queueNumberEl.innerText = data.queue_number;

        // Status UI change color logic
        if (queueStatusEl) {
          queueStatusEl.innerText = data.status;
          if (data.status === "WAITING") {
            queueStatusEl.className =
              "badge bg-warning text-dark fs-5 mt-3 mb-4";
          } else if (data.status === "CALLED") {
            queueStatusEl.className =
              "badge bg-success text-white fs-5 mt-3 mb-4";
          } else if (data.status === "SERVING") {
            queueStatusEl.className =
              "badge bg-primary text-white fs-5 mt-3 mb-4";
          } else {
            queueStatusEl.className =
              "badge bg-secondary text-white fs-5 mt-3 mb-4";
          }
        }
        // Update the people ahead and wait time
        if (peopleAheadEl) peopleAheadEl.innerText = data.people_ahead || 0;
        if (waitTimeEl) waitTimeEl.innerText = data.wait_time || 0;

        // Trigger notification: Alert when only 2 people are left
        if (
          data.status === "WAITING" &&
          data.people_ahead === 2 &&
          !hasNotifiedApproaching
        ) {
          showNotification(
            "🔔 Warm reminder: Only 2 people left ahead of you. Please proceed to the service counter.",
          );
          hasNotifiedApproaching = true;
        }
      })
      .catch((error) => console.error("Error fetching queue status:", error));
  }

  // Initial fetch
  fetchQueueStatus();

  // Fake HTTP Polling: Check the queue status every 5 seconds
  // Will change it during Week4
  const pollingInterval = setInterval(fetchQueueStatus, 5000);

  // Cancel Queue Button Click Handler
  if (cancelBtn) {
    cancelBtn.addEventListener("click", function () {
      if (confirm("Are you sure you want to cancel your queue?")) {
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
              clearInterval(pollingInterval); // Stop polling
              window.location.href = "/stores"; // Redirect to stores page
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
