document.addEventListener("DOMContentLoaded", function () {
  const walkInBtn = document.getElementById("walkInBtn");
  const checkInBtn = document.getElementById("checkInBtn");
  const selectedServiceIdInput = document.getElementById(
    "selectedServiceIdInput",
  );
  const currentApptIdInput = document.getElementById("currentApptIdInput");
  const urlParams = new URLSearchParams(window.location.search);
  const serviceIdParam = urlParams.get("service_id");
  const apptIdParam = urlParams.get("appt_id");
  if (serviceIdParam && selectedServiceIdInput) {
    selectedServiceIdInput.value = serviceIdParam;
  }
  if (apptIdParam && currentApptIdInput) {
    currentApptIdInput.value = apptIdParam;
  }

  // 1. On-site numbering logic (Walk-in)
  if (walkInBtn) {
    walkInBtn.addEventListener("click", function () {
      const requestUserId = document.getElementById("currentUserId").value;

      if (!requestUserId || requestUserId === "None") {
        alert("User ID not found. Please log in first.");
        window.location.href = "/login"; // Redirect to login page
        return;
      }

      const finalServiceId = selectedServiceIdInput
        ? selectedServiceIdInput.value
        : null;

      if (!finalServiceId) {
        alert("Service ID not found. Please select a service first.");
        return;
      }

      const payload = {
        user_id: parseInt(requestUserId),
        service_id: parseInt(finalServiceId),
      };

      fetch("/api/queues/walk-in", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            alert("Failed to obtain queue number: " + data.error);
          } else {
            alert(
              "Queue number obtained successfully! Your queue number is: " +
                data.queue_number,
            );
            window.location.href = `/dashboard?queue_id=${data.queue_id}`; // Redirect to the dashboard with queue_id
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("System busy. Please try again later.");
        });
    });
  }

  // 2. Appointment check-in logic (Check-in)
  if (checkInBtn) {
    checkInBtn.addEventListener("click", function () {
      let apptId = currentApptIdInput ? currentApptIdInput.value : null;

      if (!apptId) {
        apptId = prompt(
          "Welcome to check-in! Please enter your Appointment ID:",
        );
        if (apptId && currentApptIdInput) {
          currentApptIdInput.value = apptId;
        }
      }

      if (!apptId) {
        return;
      }

      fetch(`/api/appointments/${apptId}/check-in`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            alert("Check-in failed: " + data.error);
          } else {
            alert(
              "Check-in successful! Your queue number is: " + data.queue_number,
            );
            window.location.href = `/dashboard?queue_id=${data.queue_id}`; // Redirect to the dashboard with queue_id
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("Server not responding. Please try again later.");
        });
    });
  }
});
