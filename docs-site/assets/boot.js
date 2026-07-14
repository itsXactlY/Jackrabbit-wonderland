/* Wonderland · Hermes-on-Android Docs — pre-paint theme restore. Loaded
   synchronously in <head> (external so it satisfies a strict CSP: script-src
   'self', no inline). */
(function(){
  try{
    var t = localStorage.getItem("wl-docs-theme");
    if (t) document.documentElement.setAttribute("data-theme", t);
  } catch (e) {}
})();
