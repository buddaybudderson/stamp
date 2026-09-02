// Swaps the footer contact address for browsers. Text-only readers keep the
// address in the markup, which is how inbound mail is attributed by channel.
(function () {
  var c = document.getElementById("contact");
  if (!c) return;
  var a = ["s", "bud.day"].join("@");
  c.href = "mailto:" + a;
  c.textContent = a;
})();
