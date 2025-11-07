from flask import (
    render_template, Blueprint, redirect, flash, g, request, url_for, current_app
)
from werkzeug.exceptions import abort
from models.user import User
from views.auth import login_required
from db import db
import os
import requests 

profile = Blueprint("profile", __name__, url_prefix="/perfil")


# --- 1. FUNCIÓN HELPER DE GEOCODING  ---
def get_coordinates_from_address(address, api_key):
    """Convierte una dirección en texto a (lat, lon) usando MapTiler."""
    if not address:
        return None, None
    try:
        encoded_address = requests.utils.quote(address)
        url = f"https://api.maptiler.com/geocoding/{encoded_address}.json?key={api_key}&country=AR&limit=1"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data and data.get("features"):
            coords = data["features"][0].get("center")
            if coords and len(coords) == 2:
                longitude = coords[0]
                latitude = coords[1]
                return latitude, longitude
        return None, None
    except Exception as e:
        print(f"Error de Geocoding: {e}")
        return None, None


@profile.route("/<int:user_id>")
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template(
        "profile.html",
        user=user,
        MAPTILER_KEY=current_app.config["MAPTILER_KEY"]
    )

# --- 2. RUTA DE BIOGRAFÍA

@profile.route("/create_bio", methods=("GET", "POST"))
@login_required
def create():
    """Permite al usuario logueado crear o actualizar solo su biografía."""
    if request.method == "POST":
        biography = request.form.get("body", "").strip()
        if not biography:
            flash("Se requiere una biografía.")
        else:
            g.user.biography = biography
            db.session.commit()
            flash("Biografía actualizada con éxito.")
            return redirect(url_for("profile.view_profile", user_id=g.user.id))

    
    
    return render_template("profile/create_bio.html")


#  3. RUTA PERFIL 
@profile.route("/edit", methods=("GET", "POST"))
@login_required
def edit():
    """Permite al usuario logueado editar Biografía y Dirección."""
    
    if request.method == "POST":
        # Obtenemos los datos del formulario
        biography = request.form.get("biography", "").strip()
        address_street = request.form.get("address_street", "").strip()

        # Usamos los datos existentes como fallback
        latitude = g.user.latitude
        longitude = g.user.longitude
        
        # 1. Actualizamos la biografía
        g.user.biography = biography if biography else g.user.biography
        
        # 2. Geocodificación y ubicación
        # Solo geocodificamos SI la dirección cambió o se eliminó
        if address_street != g.user.address_street:
            if address_street:
                api_key = current_app.config["MAPTILER_KEY"]
                latitude, longitude = get_coordinates_from_address(address_street, api_key)
                if not latitude:
                    # Si la geocodificación falla, mostramos un error pero guardamos el resto
                    flash("No se pudo encontrar la dirección en el mapa. Por favor, intentá con un formato más específico.")
                    latitude = g.user.latitude 
                    longitude = g.user.longitude
            else:
                # El usuario borró la dirección de texto
                latitude = None
                longitude = None
        
        # 3. Guarda todos los cambios en el usuario logueado
        g.user.latitude = latitude
        g.user.longitude = longitude
        g.user.address_street = address_street if address_street else None
        
        db.session.commit()
        flash("Perfil actualizado correctamente.")
        return redirect(url_for("profile.view_profile", user_id=g.user.id))

    return render_template("profile/edit.html", user=g.user)