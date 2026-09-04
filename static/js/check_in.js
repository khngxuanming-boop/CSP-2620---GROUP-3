document.addEventListener("DOMContentLoaded", function () {
  const walkInBtn = document.getElementById("walkInBtn");
  const checkInBtn = document.getElementById("checkInBtn");

  // 1. On-site numbering logic (Walk-in)
  if (walkInBtn) {
    walkInBtn.addEventListener("click", function () {
      alert(
        "You have successfully joined the queue! Your queue number is: A-015",
      );
      window.location.href = "dashboard.html"; // Redirect to the dashboard
    });
  }

  // 2. Appointment check-in logic (Check-in)
  if (checkInBtn) {
    checkInBtn.addEventListener("click", function () {
      let apptId = prompt(
        "Please enter your appointment phone number or ID to check in:",
      );
      if (apptId) {
        alert(
          "Check-in successful! Appointment Status: CHECKED-IN.\nThe queue number generated for you is: A-015",
        );
        window.location.href = "dashboard.html"; // Redirect to the dashboard
      }
    });
  }
});
