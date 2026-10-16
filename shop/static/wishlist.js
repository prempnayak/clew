// Wishlist: rendered client-side from /api/wishlist.
(function () {
  var list = document.getElementById("wishlist");
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/api/wishlist");
  xhr.onload = function () {
    var items = JSON.parse(xhr.responseText);
    if (!items.length) {
      document.getElementById("wishlist-empty").hidden = false;
      return;
    }
    items.forEach(function (item) {
      var li = document.createElement("li");
      var img = document.createElement("img");
      img.src = item.image.url;
      img.alt = "";
      img.width = 48;
      var link = document.createElement("a");
      link.href = "/product/" + item.productId;
      link.textContent = item.name;
      var remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.addEventListener("click", function () {
        fetch("/api/wishlist/remove", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_id: item.productId }),
        }).then(function () { window.location.reload(); });
      });
      li.append(img, " ", link, " ", remove);
      list.appendChild(li);
    });
  };
  xhr.send();
})();
