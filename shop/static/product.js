// Product page: format the price and handle "Notify me".
(function () {
  var price = document.querySelector('[data-testid="product-price"]');
  if (price) {
    price.textContent = parseFloat(price.dataset.price).toFixed(2);
  }
  var notify = document.getElementById("notify");
  if (notify) {
    notify.addEventListener("click", function () {
      document.getElementById("notify-status").textContent = "We will email you when it is back in stock.";
    });
  }
})();
