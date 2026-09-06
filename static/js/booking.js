document.addEventListener("DOMContentLoaded", function () {
  const dateInput = document.getElementById("apptDate");
  const timeInput = document.getElementById("apptTime");
  const bookingForm = document.getElementById("bookingForm");

  // Cannot select past dates for the appointment
  if (dateInput) {
    const today = new Date();
    const localDate = new Date(
      today.getTime() - today.getTimezoneOffset() * 60000,
    )
      .toISOString()
      .split("T")[0];
    dateInput.min = localDate;
  }

  // Get open and close times from URL parameters or use default values
  const urlParams = new URLSearchParams(window.location.search);
  const openParam = urlParams.get("open");
  const closeParam = urlParams.get("close");
  const openTime = openParam !== null ? parseInt(openParam) : 8;
  const closeTime = closeParam !== null ? parseInt(closeParam) : 18;
  function generateTimeSlots(startHour, endHour) {
    if (!timeInput) return;
    timeInput.innerHTML = '<option value="">Please select a time...</option>';
    for (let i = startHour; i < endHour; i++) {
      let currentHour = i.toString().padStart(2, "0") + ":00";
      let nextHour = (i + 1).toString().padStart(2, "0") + ":00";
      let option = document.createElement("option");
      option.value = currentHour;
      option.text = `${currentHour} - ${nextHour}`;
      timeInput.appendChild(option);
    }
  }
  // Generate time slots from open time to close time
  generateTimeSlots(openTime, closeTime);

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

            const apptId = data.appointment_id;
            window.location.href = `/check-in?appt_id=${apptId}`;
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("System busy. Please try again later.");
        });
    });
  }
});
