// Arrastrar las fotos de un emprendimiento para reordenarlas.
//
// Es un agregado encima de algo que YA funciona sin JavaScript: cada slot trae
// sus botones "subir", "bajar" y "hacer principal", que son submits comunes de
// #form-reordenar con el orden resultante ya calculado en el servidor (ver
// reglas.fotos_para_reordenar). Este archivo no reemplaza eso ni lo apaga: si
// no carga, o el navegador no soporta drag and drop, o la persona no puede
// arrastrar, los botones siguen siendo el camino completo.
//
// Por eso tampoco hay una API propia: al soltar se arma la misma cadena de
// tokens que manda un boton y se envia el mismo formulario a la misma ruta. El
// servidor recibe una sola forma de dato y valida igual, venga de donde venga.
(function () {
    const contenedor = document.querySelector("[data-slots-foto]");
    const formulario = document.getElementById("form-reordenar");
    if (!contenedor || !formulario) return;

    // Los slots libres ("Libre") no son fotos y no se mueven: no tienen token.
    const slots = () => Array.from(contenedor.querySelectorAll("[data-token]"));
    if (slots().length < 2) return;

    let arrastrando = null;

    function marcarArrastrables() {
        slots().forEach((slot) => {
            slot.draggable = true;
            slot.classList.add("slot-foto--arrastrable");
        });
    }

    function limpiarMarcas() {
        slots().forEach((slot) => {
            slot.classList.remove("slot-foto--arrastrando");
            slot.classList.remove("slot-foto--destino");
        });
    }

    // El orden nuevo se manda en un campo que se crea recien aca, y no en un
    // hidden que este siempre en el HTML. Si estuviera siempre, un click en
    // "subir" mandaria dos valores de "orden" (el del hidden y el del boton) y
    // el servidor leeria el primero, que es justo el que no corresponde.
    function enviarOrden() {
        const orden = slots().map((slot) => slot.dataset.token).join(",");
        const campo = document.createElement("input");
        campo.type = "hidden";
        campo.name = "orden";
        campo.value = orden;
        formulario.appendChild(campo);
        formulario.submit();
    }

    contenedor.addEventListener("dragstart", (evento) => {
        const slot = evento.target.closest("[data-token]");
        if (!slot) return;
        arrastrando = slot;
        slot.classList.add("slot-foto--arrastrando");
        // Firefox no arranca el arrastre si no se setea algo en el dataTransfer.
        evento.dataTransfer.effectAllowed = "move";
        evento.dataTransfer.setData("text/plain", slot.dataset.token);
    });

    contenedor.addEventListener("dragover", (evento) => {
        if (!arrastrando) return;
        const destino = evento.target.closest("[data-token]");
        if (!destino || destino === arrastrando) return;
        // Sin preventDefault el navegador no considera este elemento un destino
        // valido y nunca dispara el drop.
        evento.preventDefault();
        evento.dataTransfer.dropEffect = "move";
        destino.classList.add("slot-foto--destino");
    });

    contenedor.addEventListener("dragleave", (evento) => {
        const destino = evento.target.closest("[data-token]");
        if (destino) destino.classList.remove("slot-foto--destino");
    });

    contenedor.addEventListener("drop", (evento) => {
        if (!arrastrando) return;
        const destino = evento.target.closest("[data-token]");
        if (!destino || destino === arrastrando) return;
        evento.preventDefault();

        // Antes o despues del destino segun de donde venga, que es lo que hace
        // que arrastrar "hacia arriba" y "hacia abajo" se sientan distintos.
        const actuales = slots();
        const vieneDeAntes = actuales.indexOf(arrastrando) < actuales.indexOf(destino);
        destino.insertAdjacentElement(
            vieneDeAntes ? "afterend" : "beforebegin", arrastrando
        );

        limpiarMarcas();
        arrastrando = null;
        enviarOrden();
    });

    contenedor.addEventListener("dragend", () => {
        limpiarMarcas();
        arrastrando = null;
    });

    marcarArrastrables();
})();
