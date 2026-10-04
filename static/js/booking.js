// DOMContentLoaded: make sure HTML is fully loaded before running the JS
// getElementById: get element from the form (date, time, form, service, service_id), save them in variables
document.addEventListener("DOMContentLoaded", function () {
  // Get the DOM elements from the page
  const dateInput = document.getElementById("apptDate");
  const timeInput = document.getElementById("apptTime");
  const bookingForm = document.getElementById("bookingForm");
  const storeServiceInput = document.getElementById("storeService");
  const selectedServiceIdInput = document.getElementById("selectedServiceId");

  // Cannot select past dates for the appointment
  // Get today's date and format it as YYYY-MM-DD
  // Set the min attribute of the date input to today's date
  const today = new Date();
  const localDate = new Date(
    // Adjust for timezone offset to get local date
    today.getTime() - today.getTimezoneOffset() * 60000,
  )
    .toISOString() // defaults to UTC, so adjust for timezone offset to get local date
    .split("T")[0];

  if (dateInput) {
    dateInput.min = localDate;
  }

  // Parsing URL Parameters (URLSearchParams)
  const urlParams = new URLSearchParams(window.location.search);
  const openParam = urlParams.get("open");
  const closeParam = urlParams.get("close");
  const serviceIdParam = urlParams.get("service_id");
  const serviceNameParam =
    urlParams.get("service_name") || "Card Authentication";
  // Set the service_id and service_name values in the form inputs if they exist in the URL parameters
  if (serviceIdParam && selectedServiceIdInput) {
    selectedServiceIdInput.value = serviceIdParam;
  }
  if (serviceNameParam && storeServiceInput) {
    storeServiceInput.value = decodeURIComponent(
      // decodeURIComponent to handle URL-encoded characters
      serviceNameParam.replace(/\+/g, " "), // replace '+' with space for URL-encoded spaces
    );
  }
  // Confirm the open and close time (if didn't exist, set default time form 8:00 to 18:00)
  const openTime =
    openParam && !isNaN(parseInt(openParam)) ? parseInt(openParam) : 8;
  const closeTime =
    closeParam && !isNaN(parseInt(closeParam)) ? parseInt(closeParam) : 18;

  // Dynamically generate time slots based on open and close times (generateTimeSlots function)
  function generateTimeSlots(startHour, endHour) {
    if (!timeInput) return;
    timeInput.innerHTML = '<option value="">Please select a time...</option>';
    const now = new Date();
    const selectedDate = dateInput ? dateInput.value : "";
    let addedSlotsCount = 0; // Record the number of available time slots generated
    // Loop every 30 min
    for (let minutes = startHour * 60; minutes < endHour * 60; minutes += 30) {
      // Calculate the hours and minutes for the current time and next time slot
      const hour = Math.floor(minutes / 60);
      const minute = minutes % 60;
      const nextMinutes = minutes + 30;
      const nextHour = Math.floor(nextMinutes / 60);
      const nextMinute = nextMinutes % 60;
      // Format as HH:MM (padStart to ensure two digits)
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
        // If the slot time is less than or equal to the current time, skip this slot
        if (slotTimeInMinutes <= currentTimeInMinutes) {
          continue;
        }
      }
      // Create <option> tag and add to dropdown menu
      const option = document.createElement("option");
      option.value = currentTime;
      option.text = `${currentTime} - ${nextTime}`; // e.g., "08:00 - 08:30"
      timeInput.appendChild(option);
      addedSlotsCount++;
    }
    // If date=today, and no available time slots
    if (addedSlotsCount === 0 && selectedDate === localDate) {
      timeInput.innerHTML =
        '<option value="">No available time slots today.</option>';
    }
  }

  // Generate time slots from open time to close time
  generateTimeSlots(openTime, closeTime); // execute once when page first load
  if (dateInput) {
    dateInput.addEventListener("change", function () {
      generateTimeSlots(openTime, closeTime); // user change date, re-generate time slots
    });
  }

  // Form Submission and API Requests (AJAX Submission)
  if (bookingForm) {
    bookingForm.addEventListener("submit", function (e) {
      e.preventDefault(); // Prevent the actual form submission and page refresh

      // Authentication check 1: log in or not
      const requestUserId = document.getElementById("currentUserId").value;
      if (!requestUserId || requestUserId === "None") {
        alert("User ID not found. Please log in first.");
        window.location.href = "/login"; // Didn't log in, redirect to login page
        return;
      }

      // Authentication check 2: choose service or not
      const finalServiceId = document.getElementById("selectedServiceId").value;
      if (!finalServiceId) {
        alert("Service ID not found. Please select a service first.");
        return;
      }

      // Construct the final date and time string in the format: YYYY-MM-DD HH:MM:00
      const combinedDateTime = `${dateInput.value} ${timeInput.value}:00`;

      // Construct the JSON data body will sent to backend
      const payload = {
        user_id: parseInt(requestUserId),
        service_id: parseInt(finalServiceId),
        appt_datetime: combinedDateTime,
      };

      // Send the POST request to the backend API endpoint
      // Use fetch to replace traditional form submission, so can handle the response and errors without refreshing the page
      fetch("/api/appointments", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload), // convert JS object to JSON string
      })
        .then((response) => response.json()) // Parse the JSON response from the backend
        .then((data) => {
          // Handle the response data from the backend
          if (data.error) {
            // If the backend returns an error, display it to the user
            alert("Failed to book appointment: " + data.error);
          } else {
            // Booking successful
            alert(
              "Appointment booked successfully! Appointment Status: BOOKED.",
            );
            // Proceed to check-in page,  send URL with appointment ID
            const apptId = data.appointment_id;
            window.location.replace(`/check-in?appt_id=${apptId}`);
          }
        })
        .catch((error) => {
          // Handle any network or unexpected system errors
          console.error("Error:", error);
          alert("System busy. Please try again later.");
        });
    });
  }
});
