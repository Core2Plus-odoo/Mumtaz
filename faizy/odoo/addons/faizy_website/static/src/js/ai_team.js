// Voice buttons on /ai-team. One clip plays at a time; pressing the same button again stops it.
// Plain script, no framework: the page has to work before any bundle finishes loading.
(function () {
    "use strict";
    var current = null;

    function reset(button) {
        if (!button) { return; }
        button.setAttribute("aria-pressed", "false");
        var label = button.querySelector(".fz-agent-voice-label");
        if (label) { label.textContent = button.getAttribute("data-label"); }
        button.classList.remove("is-playing");
    }

    document.addEventListener("click", function (ev) {
        var button = ev.target.closest(".fz-agent-voice");
        if (!button) { return; }
        ev.preventDefault();

        if (current && current.button === button) {
            current.audio.pause();
            reset(button);
            current = null;
            return;
        }
        if (current) {
            current.audio.pause();
            reset(current.button);
            current = null;
        }

        var audio = new Audio(button.getAttribute("data-src"));
        current = { audio: audio, button: button };
        button.setAttribute("aria-pressed", "true");
        button.classList.add("is-playing");
        var label = button.querySelector(".fz-agent-voice-label");
        if (label) { label.textContent = "Stop " + button.getAttribute("data-name"); }

        audio.addEventListener("ended", function () {
            reset(button);
            if (current && current.button === button) { current = null; }
        });
        audio.addEventListener("error", function () {
            reset(button);
            if (label) { label.textContent = "Audio unavailable"; }
            current = null;
        });
        audio.play().catch(function () {
            reset(button);
            current = null;
        });
    });
})();
