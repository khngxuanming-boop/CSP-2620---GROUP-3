document.addEventListener("DOMContentLoaded", function () {
  const dateInput = document.getElementById("apptDate");
  const timeInput = document.getElementById("apptTime");
  const bookingForm = document.getElementById("bookingForm");
  const storeServiceInput = document.getElementById("storeService");
  const selectedServiceIdInput = document.getElementyById("selectedServiceId");

  // Cannot select past dates for the appointment
  const today = new Date();
  const localDate = new Date(
    today.getTime() - today.getTimezoneOffset() * 60000,
  )
    .toISOString()
    .split("T")[0];

  if (dateInput) {
    dateInput.min = localDate;
  }

  // Get open and close times from URL parameters or use default values
  const urlParams = new URLSearchParams(window.location.search);
  const openParam = urlParams.get("open");
  const closeParam = urlParams.get("close");
  const serviceIdParam = urlParams.get("service_id") || "1";
  const serviceNameParam =
    urlParams.get("service_name") || "Card Authentication";
  if (serviceIdParam && selectedServiceIdInput) {
    selectedServiceIdInput.value = serviceIdParam;
  }
  if (serviceNameParam && storeServiceInput) {
    storeServiceInput.value = decodeURIComponent(
      serviceNameParam.replace(/\+/g, " "),
    );
  }
  const openTime =
    openParam && !isNaN(parseInt(openParam)) ? parseInt(openParam) : 8;
  const closeTime =
    closeParam && !isNaN(parseInt(closeParam)) ? parseInt(closeParam) : 18;
  function generateTimeSlots(startHour, endHour) {
    if (!timeInput) return;
    timeInput.innerHTML = '<option value="">Please select a time...</option>';
    const now = new Date();
    const selectedDate = dateInput ? dateInput.value : "";
    let addedSlotsCount = 0;
    for (let minutes = startHour * 60; minutes < endHour * 60; minutes += 30) {
      const hour = Math.floor(minutes / 60);
      const minute = minutes % 60;
      const nextMinutes = minutes + 30;
      const nextHour = Math.floor(nextMinutes / 60);
      const nextMinute = nextMinutes % 60;
      const currentTime =
        hour.toString().padStart(2, "0") +
        ":" +
        minute.toString().padStart(2, "0");
      const nextTime =
        nextHour.toString().padStart(2, "0") +
        ":" +
        nextMinute.toString().padStart(2, "0");
      // If today is selected, hide time slots that have already passed
      if (selectedDate === localDate) {
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();
        const slotTimeInMinutes = hour * 60 + minute;
        const currentTimeInMinutes = currentHour * 60 + currentMinute;
        if (slotTimeInMinutes <= currentTimeInMinutes) {
          continue;
        }
      }
      const option = document.createElement("option");
      option.value = currentTime;
      option.text = `${currentTime} - ${nextTime}`;
      timeInput.appendChild(option);
      addedSlotsCount++;
    }
    if (addedSlotsCount === 0 && selectedDate === localDate) {
      timeInput.innerHTML =
        '<option value="">Today is fully booked or closed.</option>';
    }
  }
  // Generate time slots from open time to close time
  generateTimeSlots(openTime, closeTime);
  if (dateInput) {
    dateInput.addEventListener("change", function () {
      generateTimeSlots(openTime, closeTime);
    });
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

      const finalServiceId = document.getElementById("selectedServiceId").value;
      if (!finalServiceId) {
        alert("Service ID not found. Please select a service first.");
        return;
      }

      const combinedDateTime = `${dateInput.value} ${timeInput.value}:00`;

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
