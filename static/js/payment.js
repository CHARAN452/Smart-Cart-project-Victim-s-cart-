document.getElementById("pay-btn").onclick = async function(e) {
    e.preventDefault();

    var options = {
        key: RAZORPAY_KEY,
        amount: AMOUNT * 100,
        currency: "INR",
        name: "SmartCart",
        description: "Order Payment",
        order_id: ORDER_ID,

        handler: function (response) {

            var form = document.createElement("form");
            form.method = "POST";
            form.action = "/verify-payment";

            var fields = {
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_order_id: response.razorpay_order_id,
                razorpay_signature: response.razorpay_signature,
                order_db_id: ORDER_DB_ID   // ✅ ADD THIS
            };

            for (var key in fields) {
                var input = document.createElement("input");
                input.type = "hidden";
                input.name = key;
                input.value = fields[key];
                form.appendChild(input);
            }

            document.body.appendChild(form);
            form.submit();
        }
    };

    var rzp = new Razorpay(options);
    rzp.open();
};