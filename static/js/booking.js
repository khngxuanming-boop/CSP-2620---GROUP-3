document.addEventListener("DOMContentLoaded", function () {
  const dateInput = document.getElementById("apptDate");
  const bookingForm = document.getElementById("bookingForm");

  // Cannot select past dates for the appointment
  if (dateInput) {
    dateInput.min = new Date().toISOString().split("T")[0];
  }

  // Handle form submission
  if (bookingForm) {
    bookingForm.addEventListener("submit", function (e) {
      e.preventDefault(); // Prevent the actual form submission and page refresh
      alert("Appointment booked successfully! Appointment Status: BOOKED.");

      // After the demonstration, automatically redirect to the check-in entry page
      window.location.href = "check_in.html";
    });
  }
});
