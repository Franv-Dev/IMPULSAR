/* Calendario de ferias y eventos del home.
 *
 * Consume /api/eventos/?mes=AAAA-MM (ver views/eventos_api.py) y arma una
 * grilla mensual. La lista de eventos vive AL LADO de la grilla y se lee sin
 * tocar nada; elegir un dia marcado la filtra a ese dia, y volver a tocarlo
 * (o el boton "Ver todo el mes") la devuelve al mes entero.
 *
 * Todo el DOM se arma con createElement/textContent y no con innerHTML: el
 * titulo y la descripcion de un evento los escribe un usuario, asi que
 * concatenarlos en una plantilla de HTML seria inyectable. Con textContent el
 * navegador los trata como texto y no hace falta ningun escapado a mano.
 */
(function () {
    "use strict";

    // La TARJETA, no la <section> que la envuelve: la section se llama
    // "calendario" y es el ancla de la pagina. Es la que lleva la clase
    // is-loading, asi que apuntar a la de afuera no rompe nada visible al
    // instante pero deja el gris de "cargando" sin efecto.
    var raiz = document.getElementById("calendario-card");
    if (!raiz) return;

    var grilla = document.getElementById("calendario-grid");
    var etiquetaMes = document.getElementById("calendario-mes");
    var panelLista = document.getElementById("calendario-lista");
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

    function limpiarSeleccion() {
        seleccionado = null;
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
        // Un dia elegido pertenece al mes que se esta dejando.
        limpiarSeleccion();

        if (cache[clave]) {
            // El gris se saca ACA tambien y no solo en el .then() del fetch:
            // este camino corta con el return y nunca llega alla. Y si quedo
            // una peticion vieja en vuelo, su .then() tampoco lo va a sacar,
            // porque su clave ya dejo de ser la pedida. Sin esta linea, ir
            // rapido a un mes lejano y despues volver a uno ya cacheado dejaba
            // el calendario en gris para siempre.
            raiz.classList.remove("is-loading");
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
                // Sigue con la guarda a proposito: si esta respuesta es vieja
                // y ya hay otro mes cargando, sacar el gris aca lo apagaria
                // mientras ese otro todavia esta en vuelo. Con la limpieza del
                // cache-hit de arriba ya no queda ningun camino que lo deje
                // pegado: todo lo que cambia `pedido` o lo saca en el acto
                // (cache) o se hace cargo de sacarlo despues (este fetch).
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
        } else {
            // El mes vacio ya lo dice la lista de al lado, que es donde el
            // usuario esta mirando: repetirlo abajo de la grilla lo decia dos
            // veces.
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

        // La lista se repinta junto con la grilla y no por su cuenta: depende
        // de los mismos dos datos (eventosPorDia y el dia elegido), y asi no
        // hay ningun camino que mueva uno y se olvide del otro.
        pintarLista();
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
            // aria-pressed y no aria-expanded: el dia ya no despliega nada,
            // ahora es un filtro que queda apretado o suelto.
            nodo.setAttribute("aria-pressed", seleccionado === d ? "true" : "false");
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

    /* ---------------------------------------------------------------- lista */

    function alternar(d) {
        if (seleccionado === d) {
            limpiarSeleccion();
        } else {
            seleccionado = d;
        }
        pintar(anio, mes);
        if (seleccionado !== null) {
            var elegido = grilla.querySelector(".is-selected");
            if (elegido && elegido.focus) elegido.focus();
        }
    }

    /* Los eventos que le tocan a la lista: los del dia elegido, o los de todo
     * el mes en orden de fecha. Se recorren los dias y no datos.items para no
     * depender del orden en que vino la respuesta. */
    function eventosDeLaLista() {
        if (seleccionado !== null) return eventosPorDia[seleccionado] || [];

        var todos = [];
        Object.keys(eventosPorDia)
            .map(function (d) { return parseInt(d, 10); })
            .sort(function (a, b) { return a - b; })
            .forEach(function (d) {
                todos = todos.concat(eventosPorDia[d]);
            });
        return todos;
    }

    function pintarLista() {
        // La lista es opcional: si alguna pagina reusa el calendario sin ella,
        // la grilla tiene que seguir andando igual.
        if (!panelLista) return;

        panelLista.textContent = "";

        var eventos = eventosDeLaLista();

        var cabecera = document.createElement("div");
        cabecera.className = "eventos__panel-head";

        var titulo = document.createElement("h3");
        titulo.className = "eventos__panel-titulo";
        if (seleccionado !== null) {
            var diaSemana = DIAS[(new Date(anio, mes - 1, seleccionado).getDay() + 6) % 7];
            titulo.textContent = conMayuscula(diaSemana) + " " + seleccionado +
                " de " + MESES[mes - 1];
        } else {
            titulo.textContent = "Todo " + MESES[mes - 1];
        }
        cabecera.appendChild(titulo);

        if (seleccionado !== null) {
            var volver = document.createElement("button");
            volver.type = "button";
            volver.className = "eventos__panel-volver";
            volver.textContent = "Ver todo el mes";
            volver.addEventListener("click", function () {
                limpiarSeleccion();
                pintar(anio, mes);
            });
            cabecera.appendChild(volver);
        }

        panelLista.appendChild(cabecera);

        if (eventos.length === 0) {
            var vacio = document.createElement("p");
            vacio.className = "eventos__panel-vacio";
            vacio.textContent = seleccionado !== null
                ? "Ese día no tiene eventos publicados."
                : "No hay eventos publicados este mes.";
            panelLista.appendChild(vacio);
            return;
        }

        var lista = document.createElement("ul");
        lista.className = "calendario__lista";
        eventos.forEach(function (evento) {
            lista.appendChild(tarjeta(evento));
        });
        panelLista.appendChild(lista);
    }

    function tarjeta(evento) {
        var item = document.createElement("li");
        item.className = "calendario__evento";

        var hora = document.createElement("span");
        hora.className = "calendario__evento-hora";
        // La hora es opcional en Event: "el sabado hay feria" es valido.
        hora.textContent = evento.hora || "Todo el día";
        // Mirando el mes entero, la hora sola no ubica: hace falta el dia. Se
        // corta el string en vez de construir un Date, por lo mismo que en
        // aplicar(): new Date("2026-08-14") se lee como UTC y en un huso
        // negativo cae un dia antes.
        if (seleccionado === null) {
            var dia = document.createElement("strong");
            dia.className = "calendario__evento-dia";
            dia.textContent = parseInt(String(evento.fecha).slice(8, 10), 10) +
                " de " + MESES[mes - 1];
            hora.insertBefore(dia, hora.firstChild);
        }
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
            limpiarSeleccion();
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
