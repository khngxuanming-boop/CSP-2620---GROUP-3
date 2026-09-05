document.addEventListener("DOMContentLoaded", function () {
  const dateInput = document.getElementById("apptDate");
  const timeInput = document.getElementById("apptTime");
  const bookingForm = document.getElementById("bookingForm");

  // Cannot select past dates for the appointment
  if (dateInput) {
    dateInput.min = new Date().toISOString().split("T")[0];
  }

  // Handle form submission
  if (bookingForm) {
    bookingForm.addEventListener("submit", function (e) {
      e.preventDefault(); // Prevent the actual form submission and page refresh

      const requestUserId = document.getElementById("currentUserId").value;
      if (!requestUserId || requestUserId === "None") {
        alert("User ID not found. Please log in first.");
        window.location.href = "/login";
        return;
      }

      const urlParams = new URLSearchParams(window.location.search);
      const serviceIdFromUrl = urlParams.get("service_id");
      if (!serviceIdFromUrl) {
        alert("Service ID not found. Please select a service first.");
        return;
      }

      const combinedDateTime = `${dateInput.value} ${timeInput.value}`;

      const payload = {
        user_id: parseInt(requestUserId),
        service_id: parseInt(serviceIdFromUrl),
        appt_datetime: combinedDateTime,
      };

      fetch("/api/appointments", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.error) {
            alert("Failed to book appointment: " + data.error);
          } else {
            alert(
              "Appointment booked successfully! Appointment Status: BOOKED.",
            );

            window.location.href = `/check-in?service_id=${serviceIdFromUrl}`;
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("System busy. Please try again later.");
        });
    });
  }
});
