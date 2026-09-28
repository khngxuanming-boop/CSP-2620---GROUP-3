document.addEventListener("DOMContentLoaded", function () {
  history.pushState(null, null, location.href);
  window.addEventListener("popstate", function () {
    history.pushState(null, null, location.href);
    alert(
      "You are currently in a queue. Please use the 'Cancel Queue' button to leave.",
    );
  });
  // From URL get the queue_id
  const urlParams = new URLSearchParams(window.location.search);
  const currentQueueId = urlParams.get("queue_id");

  if (!currentQueueId) {
    alert("Queue ID not found! Redirecting to home.");
    window.location.href = "/stores";
    return;
  }

  // Get references to the DOM elements
  const hiddenQueueIdEl = document.getElementById("currentQueueId");
  if (hiddenQueueIdEl) hiddenQueueIdEl.value = currentQueueId;
  const queueNumberEl = document.getElementById("queueNumberDisplay");
  const peopleAheadEl = document.getElementById("peopleAhead");
  const waitTimeEl = document.getElementById("waitTime");
  const queueStatusEl = document.getElementById("queueStatus");
  const cancelBtn = document.getElementById("cancelQueueBtn");
  const counterNameEl = document.getElementById("counterName");
  const hiddenStoreIdEl = document.getElementById("currentStoreId");

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
  const socket = io();
  let waitEndTime = null;
  let waitTimer = null;
  let lastPeopleAhead = null;
  let lastQueueStatus = null;

  function startWaitCountdown(minutes) {
    if (waitTimer) {
      clearInterval(waitTimer);
    }

    waitEndTime = Date.now() + Number(minutes || 0) * 60 * 1000;

    function updateWaitTime() {
      const remainingMs = waitEndTime - Date.now();
      const remainingMinutes = Math.max(0, Math.ceil(remainingMs / 60000));

      if (waitTimeEl) {
        waitTimeEl.innerText = remainingMinutes;
      }

      if (remainingMs <= 0) {
        clearInterval(waitTimer);
        waitTimer = null;
      }
    }

    updateWaitTime();
    waitTimer = setInterval(updateWaitTime, 1000);
  }

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
        if (data.store_id && hiddenStoreIdEl) {
          hiddenStoreIdEl.value = data.store_id;
          if (socket.connected) {
            socket.emit("join_store_room", { store_id: data.store_id });
          }
        }
        if (queueNumberEl) queueNumberEl.innerText = data.queue_number;

        if (data.store_name) {
          const storeNameEl = document.getElementById("storeName");
          if (storeNameEl) storeNameEl.innerText = data.store_name;
        }
        if (data.service_name) {
          const serviceNameEl = document.getElementById("serviceName");
          if (serviceNameEl) serviceNameEl.innerText = data.service_name;
        }

        // Status UI change color logic
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
        // Update the people ahead and wait time
        if (peopleAheadEl) peopleAheadEl.innerText = data.people_ahead ?? 0;
        if (data.status === "WAITING") {
          if (
            waitEndTime === null ||
            lastPeopleAhead !== data.people_ahead ||
            lastQueueStatus !== data.status
          ) {
            startWaitCountdown(data.wait_time ?? 0);
          }
        } else {
          if (waitTimer) {
            clearInterval(waitTimer);
            waitTimer = null;
          }

          waitEndTime = null;

          if (waitTimeEl) {
            waitTimeEl.innerText = 0;
          }
        }
        if (counterNameEl) {
          counterNameEl.innerText = data.counter_name ?? "-";
        }

        if (lastQueueStatus && lastQueueStatus !== data.status) {
          if (data.status === "SERVING") {
            alert(
              `🎉 It is your turn! Please proceed to ${data.counter_name ?? "the counter"}.`,
            );
            showNotification(
              `Is is your turn at ${data.counter_name ?? "the counter"}!`,
            );
          } else if (data.status === "COMPLETED") {
            alert("✅ Your service is completed. Thank you!");
          } else if (data.status === "SKIPPED") {
            alert("⚠️ You have been skipped. Please contact the staff.");
          } else if (data === "CANCELED") {
            alert("❌ Your queue has been cancelled.");
          }
        }

        // Trigger notification: Alert when only 2 people are left
        if (data.status === "WAITING") {
          if (
            data.people_ahead <= 2 &&
            data.people_ahead > 0 &&
            !hasNotifiedApproaching
          ) {
            showNotification(
              "🔔 Warm reminder: It is almost your turn! Please proceed to the service counter.",
            );
            hasNotifiedApproaching = true;
          } else if (data.people_ahead > 2) {
            hasNotifiedApproaching = false;
          }
        }

        lastPeopleAhead = data.people_ahead;
        lastQueueStatus = data.status;
      })
      .catch((error) => console.error("Error fetching queue status:", error));
  }

  // Initial fetch
  fetchQueueStatus();

  // Socket.IO: Real time queue update
  socket.on("connect", function () {
    console.log("WebSocket connected successfully!");
    if (hiddenStoreIdEl && hiddenStoreIdEl.value) {
      socket.emit("join_store_room", { store_id: hiddenStoreIdEl.value });
    }
    fetchQueueStatus();
  });
  socket.on("queue_status_updated", function (data) {
    console.log("Queue data changed! Fetching new status instantly...");
    fetchQueueStatus();
  });
  socket.on("disconnect", function () {
    console.log("WebSocket disconnected.");
  });

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
              cancelBtn.innerText = "Back to stores";
              cancelBtn.className = "btn btn-secondary w-100 mt-3";
              const newBtn = cancelBtn.cloneNode(true);
              cancelBtn.parentNode.replaceChild(newBtn, cancelBtn);
              newBtn.addEventListener("click", function () {
                window.location.href = "/stores";
              });
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
