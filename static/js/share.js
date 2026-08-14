// Compartir un emprendimiento: Web Share API si el navegador la soporta
// (tipico en mobile), o copiar el link al portapapeles como respaldo.
//
// Escucha en document en vez de atar un listener a cada boton: las tarjetas
// del home se re-renderizan por JS en cada busqueda (ver main.js), asi que
// atar el listener una sola vez al cargar la pagina no alcanzaria.

async function compartirEmprendimiento(boton) {
    const url = boton.dataset.shareUrl;
    const title = boton.dataset.shareTitle || document.title;

    if (navigator.share) {
        try {
            await navigator.share({ title, url });
        } catch (err) {
            // El usuario cerro el dialogo nativo sin elegir nada: no es un error.
        }
        return;
    }

    try {
        await navigator.clipboard.writeText(url);
        avisarLinkCopiado(boton);
    } catch (err) {
        // Sin permiso de portapapeles (o navegador muy viejo): al menos que
        // pueda copiarlo a mano.
        window.prompt("Copiá el link para compartir:", url);
    }
}

function avisarLinkCopiado(boton) {
    const textoOriginal = boton.textContent;
    boton.textContent = "✓ Copiado";
    boton.classList.add("share-btn--copied");
    boton.disabled = true;

    setTimeout(() => {
        boton.textContent = textoOriginal;
        boton.classList.remove("share-btn--copied");
        boton.disabled = false;
    }, 2000);
}

document.addEventListener("click", (event) => {
    const boton = event.target.closest(".share-btn");
    if (!boton) return;

    event.preventDefault();
    compartirEmprendimiento(boton);
});
