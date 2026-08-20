// Chat simple sin tiempo real: el historial inicial viene renderizado por el
// servidor (JSON embebido) y despues se hace polling para traer mensajes
// nuevos de la otra parte, sin recargar la pagina.

function escapeHtmlChat(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function formatearHoraChat(iso) {
    if (!iso) return "";
    try {
        return new Date(iso).toLocaleString("es-AR", {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch (err) {
        return "";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const contenedor = document.getElementById("chat-historial");
    if (!contenedor) return; // no estamos en una conversacion

    const postId = contenedor.dataset.postId;
    const clientId = contenedor.dataset.clientId;
    const miId = Number(contenedor.dataset.myId);

    const dataEl = document.getElementById("chat-historial-data");
    let historial = [];
    try {
        historial = dataEl ? JSON.parse(dataEl.textContent) : [];
    } catch (err) {
        historial = [];
    }

    function agregarMensaje(m) {
        const vacio = document.getElementById("chat-empty");
        if (vacio) vacio.remove();

        const burbuja = document.createElement("div");
        burbuja.className =
            "chat-message " + (m.sender_id === miId ? "chat-message--mine" : "chat-message--theirs");
        burbuja.dataset.messageId = m.id;
        burbuja.innerHTML = `
            <p class="chat-message__body">${escapeHtmlChat(m.body)}</p>
            <span class="chat-message__meta">${escapeHtmlChat(m.sender_username)} · ${formatearHoraChat(m.created)}</span>
        `;
        contenedor.appendChild(burbuja);
    }

    function mostrarVacioSiCorresponde() {
        if (contenedor.children.length > 0) return;
        const vacio = document.createElement("p");
        vacio.className = "reviews-empty";
        vacio.id = "chat-empty";
        vacio.textContent = "Todavía no hay mensajes. ¡Escribí el primero!";
        contenedor.appendChild(vacio);
    }

    let ultimoId = 0;
    historial.forEach((m) => {
        agregarMensaje(m);
        ultimoId = Math.max(ultimoId, m.id);
    });
    mostrarVacioSiCorresponde();
    contenedor.scrollTop = contenedor.scrollHeight;

    function buscarNuevos() {
        fetch(`/mensajes/${postId}/${clientId}/nuevos?after=${ultimoId}`)
            .then((res) => (res.ok ? res.json() : Promise.reject(res)))
            .then((data) => {
                const nuevos = Array.isArray(data.items) ? data.items : [];
                if (nuevos.length === 0) return;

                nuevos.forEach((m) => {
                    agregarMensaje(m);
                    ultimoId = Math.max(ultimoId, m.id);
                });
                contenedor.scrollTop = contenedor.scrollHeight;
            })
            .catch(() => {
                // Un polling fallido (ej. se cayó la red un instante) no debe
                // interrumpir el chat: se reintenta solo en la proxima vuelta.
            });
    }

    setInterval(buscarNuevos, 4000);
});
