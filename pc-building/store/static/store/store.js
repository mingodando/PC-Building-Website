// Quantity steppers: the −/+ buttons next to a number input.
// Add data-autosubmit to submit the surrounding form after a change (used in the cart).
document.querySelectorAll('[data-stepper]').forEach(function (stepper) {
    var input = stepper.querySelector('input');
    var autosubmit = stepper.hasAttribute('data-autosubmit');
    var timer;

    function clamp(value) {
        var min = input.min === '' ? -Infinity : Number(input.min);
        var max = input.max === '' ? Infinity : Number(input.max);
        return Math.min(Math.max(value, min), max);
    }

    function changed() {
        if (!autosubmit) return;
        clearTimeout(timer);
        timer = setTimeout(function () { input.form.submit(); }, 450);
    }

    stepper.querySelectorAll('[data-step]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var next = clamp((Number(input.value) || 0) + Number(btn.dataset.step));
            if (String(next) !== input.value) {
                input.value = next;
                changed();
            }
        });
    });
    input.addEventListener('change', function () {
        input.value = clamp(Number(input.value) || 0);
        changed();
    });
});

// Checkout: update the delivery fee and total when the delivery option changes.
(function () {
    var total = document.getElementById('order-total');
    var fee = document.getElementById('shipping-fee');
    if (!total || !fee) return;
    var subtotal = Number(total.dataset.subtotal);
    var fmt = function (n) {
        return '฿' + n.toLocaleString('en-US', {
            minimumFractionDigits: n % 1 ? 2 : 0,
            maximumFractionDigits: 2,
        });
    };
    document.querySelectorAll('input[name="delivery_method"]').forEach(function (radio) {
        radio.addEventListener('change', function () {
            var shipping = Number(radio.dataset.fee);
            fee.textContent = shipping ? fmt(shipping) : 'Free';
            total.textContent = fmt(subtotal + shipping);
        });
    });
})();
