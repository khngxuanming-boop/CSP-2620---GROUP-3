// DOMContentLoaded: make sure HTML is fully loaded before running the JS
document.addEventListener("DOMContentLoaded", function () {
  // Get the DOM elements for buttons and hidden inputs
  const walkInBtn = document.getElementById("walkInBtn");
  const checkInBtn = document.getElementById("checkInBtn");
  const selectedServiceIdInput = document.getElementById(
    "selectedServiceIdInput",
  );

  // Parse URL parameters to auto-fill inputs
  const currentApptIdInput = document.getElementById("currentApptIdInput");
  const urlParams = new URLSearchParams(window.location.search);
  const serviceIdParam = urlParams.get("service_id");
  const apptIdParam = urlParams.get("appt_id");

  // Auto-populate the input fields if the parameters exist in the URL
  if (serviceIdParam && selectedServiceIdInput) {
    selectedServiceIdInput.value = serviceIdParam;
  }
  if (apptIdParam && currentApptIdInput) {
    currentApptIdInput.value = apptIdParam;
  }

  // 1. On-site numbering logic (Walk-in)
  // Handle user who walk into the store without an appointment
  if (walkInBtn) {
    walkInBtn.addEventListener("click", function () {
      // Authentication check: Ensure the user is logged in and has a valid user ID
      const requestUserId = document.getElementById("currentUserId").value;

      if (!requestUserId || requestUserId === "None") {
        alert("User ID not found. Please log in first.");
        window.location.href = "/login"; // Redirect to login page
        return;
      }

      // Authentication check: Ensure the user has selected a service
      const finalServiceId = selectedServiceIdInput
        ? selectedServiceIdInput.value
        : null;

      if (!finalServiceId) {
        alert("Service ID not found. Please select a service first.");
        return;
      }

      // Construct the payload object to send to the backend
      const payload = {
        user_id: parseInt(requestUserId),
        service_id: parseInt(finalServiceId),
      };

      // Send the POST request to the backend API endpoint to create a new walk-in queue entry
      // Use fetch to replace traditional form submission, so can handle the response and errors without refreshing the page
      fetch("/api/queues/walk-in", {
        method: "POST", // creating new resource
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload), // convert JS object to JSON string
      })
        .then((response) => response.json()) // Parse the JSON response string back into a JS object
        .then((data) => {
          if (data.error) {
            // If the backend returns an error, display it to the user
            alert("Failed to obtain queue number: " + data.error);
          } else {
            // Success workflow
            alert(
              "Queue number obtained successfully! Your queue number is: " +
                data.queue_number,
            );
            // use location.replace to avoid the user going back to the previous page with the back button, which may cause confusion
            window.location.replace(`/dashboard?queue_id=${data.queue_id}`); // Redirect to the dashboard with queue_id
          }
        })
        .catch((error) => {
          // Fallback error handling for network or unexpected system errors
          console.error("Error:", error);
          alert("System busy. Please try again later.");
        });
    });
  }

  // 2. Appointment check-in logic (Check-in)
  // Handle user who has an appointment and wants to check in
  if (checkInBtn) {
    checkInBtn.addEventListener("click", function () {
      let apptId = currentApptIdInput ? currentApptIdInput.value : null;

      // If appt_id is missing (e.g., user didn't come via a direct check-in link), prompt them to enter it manually
      if (!apptId) {
        apptId = prompt(
          "Welcome to check-in! Please enter your Appointment ID (Numbers only):",
        );
        // Validate the input to ensure it's a number
        if (apptId && isNaN(parseInt(apptId))) {
          alert("Invalid ID format. Please enter number only.");
          return;
        }
        // Save the valid manual input back into the hidden field
        if (apptId && currentApptIdInput) {
          currentApptIdInput.value = apptId;
        }
      }

      // If user clicked "Cancel" on the prompt or left it blank, stop the check-in process
      if (!apptId) {
        return;
      }

      // Send a PUT request to the backend API endpoint to check in the appointment
      fetch(`/api/appointments/${apptId}/check-in`, {
        method: "PUT", // updating appointment resource
        headers: {
          "Content-Type": "application/json",
        },
      })
        .then((response) => response.json()) // Parse JSON response
        .then((data) => {
          if (data.error) {
            alert("Check-in failed: " + data.error);
          } else {
            alert(
              "Check-in successful! Your queue number is: " + data.queue_number,
            );
            // redirect to dashboard page
            window.location.replace(`/dashboard?queue_id=${data.queue_id}`); // Redirect to the dashboard with queue_id
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("Server not responding. Please try again later.");
        });
    });
  }
});
