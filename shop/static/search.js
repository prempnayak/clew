// Search results: "Add to cart" posts the result's product to the cart, then opens the cart.
(function () {
  var results = JSON.parse(document.getElementById("results-data").textContent);
  document.querySelectorAll("button.add").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var result = results[btn.dataset.index];
      var productId = result.productId;
      fetch("/api/cart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId }),
      }).then(function () {
        window.location.href = "/cart";
      });
    });
  });
})();
