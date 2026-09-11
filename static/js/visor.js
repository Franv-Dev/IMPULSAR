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

    // Lo que el Tab puede alcanzar adentro del visor. Se recalcula en cada
    // Tab y no se guarda una vez: las fotos se muestran y se esconden con
    // `hidden` mientras el visor está abierto.
    const FOCUSABLES =
        'a[href], button:not([disabled]), input:not([disabled]), ' +
        'select:not([disabled]), textarea:not([disabled]), ' +
        '[tabindex]:not([tabindex="-1"])';

    function focosDelVisor() {
        return Array.from(visor.querySelectorAll(FOCUSABLES)).filter(
            (elemento) => !elemento.hidden && elemento.offsetParent !== null
        );
    }

    // El foco no se va de acá mientras el visor esté abierto.
    //
    // Sin esto, tabular desde la flecha «siguiente» salía del overlay y
    // recorría la página tapada, que sigue entera y enfocable: 54 elementos
    // alcanzables detrás de un diálogo que visualmente los cubre. aria-modal
    // arregla la mitad del problema (lo que anuncia un lector de pantalla),
    // pero no mueve el Tab: eso es esto.
    function encerrarElFoco(evento) {
        const focos = focosDelVisor();
        if (!focos.length) {
            evento.preventDefault();
            return;
        }

        const primero = focos[0];
        const ultimo = focos[focos.length - 1];
        const activo = document.activeElement;

        // Con el foco afuera (se llegó clickeando el fondo, por ejemplo) el
        // Tab siguiente se iría a la página de atrás: se lo trae al principio.
        if (!visor.contains(activo)) {
            evento.preventDefault();
            primero.focus();
            return;
        }

        if (evento.shiftKey && activo === primero) {
            evento.preventDefault();
            ultimo.focus();
        } else if (!evento.shiftKey && activo === ultimo) {
            evento.preventDefault();
            primero.focus();
        }
    }

    document.addEventListener("keydown", (evento) => {
        if (visor.hidden) return;
        if (evento.key === "Escape") cerrar();
        if (evento.key === "ArrowLeft") mostrar(actual - 1);
        if (evento.key === "ArrowRight") mostrar(actual + 1);
        if (evento.key === "Tab") encerrarElFoco(evento);
    });
});
