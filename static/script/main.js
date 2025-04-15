function showToastMessage(message, success) {
   Toastify({
      text: message,
      duration: 3000,
      gravity: "top",
      position: "right",
      stopOnFocus: true,
      style: {
         background: success ? "#4BB543" : "#FF0000"
      }
   }).showToast();
}