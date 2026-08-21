/* Calendario de ferias y eventos del home.
 *
 * Consume /api/eventos/?mes=AAAA-MM (ver views/eventos_api.py) y arma una
 * grilla mensual. Tocar un dia con eventos despliega un panel ABAJO de la
 * grilla, sin taparla y sin modal.
 *
 * Todo el DOM se arma con createElement/textContent y no con innerHTML: el
 * titulo y la descripcion de un evento los escribe un usuario, asi que
 * concatenarlos en una plantilla de HTML seria inyectable. Con textContent el
 * navegador los trata como texto y no hace falta ningun escapado a mano.
 */
(function () {
    "use strict";

    var raiz = document.getElementById("calendario");
    if (!raiz) return;

    var grilla = document.getElementById("calendario-grid");
    var etiquetaMes = document.getElementById("calendario-mes");
    var expand = document.getElementById("calendario-expand");
    var expandContent = document.getElementById("calendario-expand-content");
    var estado = document.getElementById("calendario-estado");
    var btnPrev = document.getElementById("calendario-prev");
    var btnNext = document.getElementById("calendario-next");

    // Escritos y no sacados de toLocaleString: eso depende del locale del
    // navegador y dejaria "August" en pantalla. Mismo criterio que MESES en
    // services/eventos.py.
    var MESES = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ];
    // Lunes primero, igual que services/horarios.DIAS.
    var DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];

    // Cuantos puntos se dibujan como maximo en un dia. Mas que esto no entra en
    // la celda y ademas no aporta: el numero exacto lo dice el panel.
    var MAX_PUNTOS = 3;

    var anio = null;
    var mes = null;          // 1-12
    var hoy = null;          // "AAAA-MM-DD" segun el reloj de Argentina, lo da la API
    var eventosPorDia = {};  // { 14: [evento, ...] }
    var seleccionado = null; // numero de dia abierto, o null
    var cache = {};          // { "2026-08": {items, hoy} }, para no re-pedir al volver
    // El mes que se esta esperando de la API. Sirve para descartar una
    // respuesta que llega tarde: si el usuario ya se movio a otro mes, sus
    // eventos no tienen que pisar los del mes que esta mirando ahora.
    var pedido = null;

    function conMayuscula(texto) {
        // A mano y no con text-transform: capitalize, que capitaliza CADA
        // palabra y dejaba "Jueves De Agosto".
        return texto.charAt(0).toUpperCase() + texto.slice(1);
    }

    function claveMes(a, m) {
        return String(a) + "-" + (m < 10 ? "0" : "") + String(m);
    }

    function claveDia(a, m, d) {
        return claveMes(a, m) + "-" + (d < 10 ? "0" : "") + String(d);
    }

    function mostrarEstado(texto) {
        if (!texto) {
            estado.hidden = true;
            estado.textContent = "";
            return;
        }
        estado.hidden = false;
        estado.textContent = texto;
    }

    function cerrarPanel() {
        seleccionado = null;
        expand.classList.remove("is-open");
    }

    /* ---------------------------------------------------------------- datos */

    /* Muestra ese mes: pinta la grilla EN EL ACTO y despues le mete los puntos
     * cuando llega la respuesta.
     *
     * El mes se mueve al instante y no al resolver el fetch, que es como estaba
     * antes y andaba mal: `mes` solo se actualizaba dentro de pintar(), asi que
     * dos clicks seguidos en la flecha calculaban los dos a partir del mismo
     * mes viejo, y ademas el segundo se descartaba si el primero todavia estaba
     * en vuelo. Probado: cuatro clicks seguidos desde septiembre terminaban en
     * diciembre en vez de enero. Ahora cada click avanza uno, siempre.
     */
    function irA(a, m) {
        anio = a;
        mes = m;
        var clave = claveMes(a, m);
        pedido = clave;
        // Un dia abierto pertenece al mes que se esta dejando.
        cerrarPanel();

        if (cache[clave]) {
            aplicar(cache[clave], a, m);
            return;
        }

        // La grilla del mes nuevo se dibuja ya, sin puntos: el mes cambia
        // apenas se toca la flecha aunque la red tarde.
        eventosPorDia = {};
        pintar(a, m);
        mostrarEstado("");
        raiz.classList.add("is-loading");

        fetch("/api/eventos/?mes=" + encodeURIComponent(clave), {
            headers: { "Accept": "application/json" }
        })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (datos) {
                cache[clave] = datos;
                if (pedido !== clave) return;
                aplicar(datos, a, m);
            })
            .catch(function () {
                if (pedido !== clave) return;
                // La grilla ya esta dibujada y vacia; solo falta explicar por
                // que no hay puntos.
                mostrarEstado("No se pudieron cargar los eventos. Probá de nuevo más tarde.");
            })
            .then(function () {
                if (pedido === clave) raiz.classList.remove("is-loading");
            });
    }

    function aplicar(datos, a, m) {
        hoy = datos.hoy;
        eventosPorDia = {};
        (datos.items || []).forEach(function (evento) {
            // "2026-08-14" -> 14. Se corta el string en vez de construir un
            // Date: new Date("2026-08-14") se interpreta como UTC y en un huso
            // negativo cae un dia antes.
            var dia = parseInt(String(evento.fecha).slice(8, 10), 10);
            if (!eventosPorDia[dia]) eventosPorDia[dia] = [];
            eventosPorDia[dia].push(evento);
        });
        pintar(a, m);
        if (datos.truncado) {
            mostrarEstado("Este mes tiene muchos eventos: se muestran los primeros " + datos.total + ".");
        } else if (!datos.items || datos.items.length === 0) {
            mostrarEstado("No hay eventos publicados este mes.");
        } else {
            mostrarEstado("");
        }
    }

    /* -------------------------------------------------------------- pintado */

    function pintar(a, m) {
        anio = a;
        mes = m;
        etiquetaMes.textContent = conMayuscula(MESES[m - 1]) + " " + a;

        grilla.textContent = "";

        // getDay() da 0=domingo; la grilla arranca en lunes.
        var primerDiaSemana = (new Date(a, m - 1, 1).getDay() + 6) % 7;
        // Dia 0 del mes siguiente = ultimo dia de este.
        var largo = new Date(a, m, 0).getDate();

        for (var i = 0; i < primerDiaSemana; i++) {
            var hueco = document.createElement("div");
            hueco.className = "calendario__dia calendario__dia--vacio";
            hueco.setAttribute("aria-hidden", "true");
            grilla.appendChild(hueco);
        }

        for (var d = 1; d <= largo; d++) {
            grilla.appendChild(celda(a, m, d));
        }
    }

    function celda(a, m, d) {
        var eventos = eventosPorDia[d] || [];
        var tiene = eventos.length > 0;
        // Solo los dias con eventos son botones: un dia vacio no hace nada, y
        // volverlo foco de teclado obligaria a tabular 30 veces para pasar el
        // calendario.
        var nodo = document.createElement(tiene ? "button" : "div");
        nodo.className = "calendario__dia";

        if (tiene) {
            nodo.type = "button";
            nodo.classList.add("has-events");
            nodo.setAttribute(
                "aria-label",
                d + " de " + MESES[m - 1] + ", " + eventos.length +
                (eventos.length === 1 ? " evento" : " eventos")
            );
            nodo.setAttribute("aria-expanded", seleccionado === d ? "true" : "false");
            nodo.addEventListener("click", function () { alternar(d); });
        }
        if (claveDia(a, m, d) === hoy) nodo.classList.add("is-today");
        if (seleccionado === d) nodo.classList.add("is-selected");

        var numero = document.createElement("span");
        numero.className = "calendario__dia-num";
        numero.textContent = String(d);
        nodo.appendChild(numero);

        var puntos = document.createElement("span");
        puntos.className = "calendario__puntos";
        for (var i = 0; i < Math.min(eventos.length, MAX_PUNTOS); i++) {
            var punto = document.createElement("span");
            punto.className = "calendario__punto";
            puntos.appendChild(punto);
        }
        // Siempre se agrega, con o sin puntos: reserva el alto y evita que el
        // numero salte de posicion entre un dia con eventos y uno sin.
        nodo.appendChild(puntos);

        return nodo;
    }

    /* ---------------------------------------------------------------- panel */

    function alternar(d) {
        if (seleccionado === d) {
            cerrarPanel();
        } else {
            seleccionado = d;
            pintarPanel(d);
            expand.classList.add("is-open");
        }
        pintar(anio, mes);
        if (seleccionado !== null) {
            var abierto = grilla.querySelector(".is-selected");
            if (abierto && abierto.focus) abierto.focus();
        }
    }

    function pintarPanel(d) {
        var eventos = eventosPorDia[d] || [];
        expandContent.textContent = "";

        var cabecera = document.createElement("div");
        cabecera.className = "calendario__panel-head";

        var numero = document.createElement("span");
        numero.className = "calendario__panel-num";
        numero.textContent = String(d);
        cabecera.appendChild(numero);

        var etiqueta = document.createElement("span");
        etiqueta.className = "calendario__panel-fecha";
        var diaSemana = DIAS[(new Date(anio, mes - 1, d).getDay() + 6) % 7];
        etiqueta.textContent = conMayuscula(diaSemana) + " de " + MESES[mes - 1];
        cabecera.appendChild(etiqueta);

        var cerrar = document.createElement("button");
        cerrar.type = "button";
        cerrar.className = "calendario__panel-cerrar";
        cerrar.setAttribute("aria-label", "Cerrar el detalle del día");
        cerrar.textContent = "✕";
        cerrar.addEventListener("click", function () {
            cerrarPanel();
            pintar(anio, mes);
        });
        cabecera.appendChild(cerrar);

        expandContent.appendChild(cabecera);

        var lista = document.createElement("ul");
        lista.className = "calendario__lista";
        eventos.forEach(function (evento) {
            lista.appendChild(tarjeta(evento));
        });
        expandContent.appendChild(lista);
    }

    function tarjeta(evento) {
        var item = document.createElement("li");
        item.className = "calendario__evento";

        var hora = document.createElement("span");
        hora.className = "calendario__evento-hora";
        // La hora es opcional en Event: "el sabado hay feria" es valido.
        hora.textContent = evento.hora || "Todo el día";
        item.appendChild(hora);

        var barra = document.createElement("span");
        barra.className = "calendario__evento-barra";
        barra.setAttribute("aria-hidden", "true");
        item.appendChild(barra);

        var cuerpo = document.createElement("div");
        cuerpo.className = "calendario__evento-cuerpo";

        var titulo = document.createElement("a");
        titulo.className = "calendario__evento-titulo";
        titulo.href = evento.url;
        titulo.textContent = evento.titulo;
        cuerpo.appendChild(titulo);

        var meta = document.createElement("p");
        meta.className = "calendario__evento-meta";
        meta.textContent = evento.emprendimiento;
        cuerpo.appendChild(meta);

        if (evento.descripcion) {
            var desc = document.createElement("p");
            desc.className = "calendario__evento-desc";
            desc.textContent = evento.descripcion;
            cuerpo.appendChild(desc);
        }

        item.appendChild(cuerpo);
        return item;
    }

    /* ------------------------------------------------------------ navegacion */

    function moverMes(delta) {
        // Todavia no llego la primera respuesta y no se sabe en que mes se
        // esta: sin esto, mes es null y null + 1 da NaN.
        if (mes === null) return;
        var m = mes + delta;
        var a = anio;
        if (m < 1) { m = 12; a -= 1; }
        if (m > 12) { m = 1; a += 1; }
        irA(a, m);
    }

    btnPrev.addEventListener("click", function () { moverMes(-1); });
    btnNext.addEventListener("click", function () { moverMes(1); });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && seleccionado !== null) {
            cerrarPanel();
            pintar(anio, mes);
        }
    });

    // Primer pedido sin ?mes: el servidor contesta con el mes en curso segun el
    // reloj de Argentina y dice cual uso, asi el arranque no depende del huso
    // del visitante.
    (function inicial() {
        // Centinela: hasta que no se sepa que mes contesto el servidor no hay
        // clave con que compararse. Si el usuario alcanza a tocar una flecha
        // antes, irA() pisa `pedido` y esta respuesta se descarta en vez de
        // devolverlo al mes actual de un salto.
        pedido = "inicial";
        raiz.classList.add("is-loading");
        fetch("/api/eventos/", { headers: { "Accept": "application/json" } })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (datos) {
                cache[datos.mes] = datos;
                if (pedido !== "inicial") return;
                pedido = datos.mes;
                var partes = String(datos.mes).split("-");
                aplicar(datos, parseInt(partes[0], 10), parseInt(partes[1], 10));
            })
            .catch(function () {
                if (pedido !== "inicial") return;
                // Sin respuesta no se sabe el mes de Argentina; el del navegador
                // es lo mejor que queda y como mucho se equivoca en el borde.
                var ahora = new Date();
                eventosPorDia = {};
                pintar(ahora.getFullYear(), ahora.getMonth() + 1);
                mostrarEstado("No se pudieron cargar los eventos. Probá de nuevo más tarde.");
            })
            .then(function () {
                raiz.classList.remove("is-loading");
            });
    })();
})();
