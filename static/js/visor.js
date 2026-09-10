// =============================
// VISOR DE FOTOS DE LA FICHA
// =============================
// Antes las miniaturas de la galería eran <a> al archivo suelto de
// /static/uploads/: abrían la foto cruda en una pestaña nueva, sin el nombre
// del emprendimiento, sin las otras fotos y sin forma de volver que no fuera
// cerrar la pestaña. Ahora se abren acá adentro.
//
// El visor vive en el HTML con `hidden` puesto, y las fotos también: si el JS
// no carga, la galería de arriba se sigue viendo y sólo se pierde el agrandar,
// que es exactamente lo que tiene que pasar.

document.addEventListener("DOMContentLoaded", () => {
    const visor = document.getElementById("visor");
    if (!visor) return; // esta ficha no tiene fotos, o tiene una sola

    const fotos = Array.from(visor.querySelectorAll("[data-visor-foto]"));
    const pie = visor.querySelector("[data-visor-pie]");
    if (!fotos.length) return;

    // Quién tenía el foco antes de abrir, para devolvérselo al cerrar: sin
    // esto, cerrar el visor con Escape deja el foco en el <body> y hay que
    // tabular desde el principio de la página.
    let disparador = null;
    let actual = 0;

    function mostrar(indice) {
        actual = (indice + fotos.length) % fotos.length;
        fotos.forEach((foto, n) => { foto.hidden = n !== actual; });
        if (pie) pie.textContent = `${actual + 1} de ${fotos.length}`;
    }

    function abrir(indice, desde) {
        disparador = desde || null;
        visor.hidden = false;
        document.body.classList.add("con-visor");
        mostrar(indice);
        const cerrar = visor.querySelector(".visor__cerrar");
        if (cerrar) cerrar.focus();
    }

    function cerrar() {
        visor.hidden = true;
        document.body.classList.remove("con-visor");
        if (disparador) disparador.focus();
    }

    document.querySelectorAll("[data-visor]").forEach((boton) => {
        boton.addEventListener("click", () => {
            abrir(Number(boton.dataset.visor) || 0, boton);
        });
    });

    visor.querySelectorAll("[data-visor-cerrar]").forEach((elemento) => {
        elemento.addEventListener("click", cerrar);
    });

    visor.querySelectorAll("[data-visor-mover]").forEach((boton) => {
        boton.addEventListener("click", () => {
            mostrar(actual + Number(boton.dataset.visorMover));
        });
    });

    document.addEventListener("keydown", (evento) => {
        if (visor.hidden) return;
        if (evento.key === "Escape") cerrar();
        if (evento.key === "ArrowLeft") mostrar(actual - 1);
        if (evento.key === "ArrowRight") mostrar(actual + 1);
    });
});
