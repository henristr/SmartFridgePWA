from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import json
import os
import google.generativeai as genai
from config import GEMINI_API_KEY
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "mega-geheimes-passwort"  # für Sessions
app.jinja_env.globals.update(enumerate=enumerate)

DATEI = "produkte.json"
USER_DATEI = "users.json"
REZEPTE_DATEI = "rezepte.json"


# ------------------ PRODUKTE LADEN ------------------
def lade_produkte():
    if os.path.exists(DATEI):
        with open(DATEI, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {}


def speichere_produkte(produkte):
    with open(DATEI, "w", encoding="utf-8") as f:
        json.dump(produkte, f, ensure_ascii=False, indent=2)


produkte = lade_produkte()


# ------------------ BENUTZER LADEN ------------------
def lade_users():
    if os.path.exists(USER_DATEI):
        with open(USER_DATEI, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {"admin": "admin"}  # Standard-Admin


def speichere_users(users):
    with open(USER_DATEI, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


users = lade_users()


# ------------------ REZEPTE LADEN UND SPEICHERN ------------------
def lade_rezepte():
    if os.path.exists(REZEPTE_DATEI):
        with open(REZEPTE_DATEI, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {}


def speichere_rezepte(rezepte):
    with open(REZEPTE_DATEI, "w", encoding="utf-8") as f:
        json.dump(rezepte, f, ensure_ascii=False, indent=2)


def bereinige_alte_rezepte(user_rezepte):
    """Entfernt Rezepte, die älter als 7 Tage sind und nicht favorisiert sind"""
    heute = datetime.now()
    gefilterte_rezepte = []

    for rezept in user_rezepte:
        erstellt_am = datetime.fromisoformat(rezept.get("created_at", heute.isoformat()))
        tage_alt = (heute - erstellt_am).days
        ist_favorit = rezept.get("is_favorite", False)

        # Behalte Rezept, wenn es favorisiert ist oder jünger als 7 Tage
        if ist_favorit or tage_alt < 7:
            gefilterte_rezepte.append(rezept)

    return gefilterte_rezepte


rezepte = lade_rezepte()


# ------------------ KI REZEPT GENERATOR MIT GEMINI AI ------------------

# Konfiguriere Gemini API (API Key aus config.py)
if GEMINI_API_KEY and GEMINI_API_KEY != "HIER_DEINEN_API_KEY_EINTRAGEN":
    genai.configure(api_key=GEMINI_API_KEY)


def generiere_rezept(produkte_liste):
    """
    Generiert ein intelligentes Rezept basierend auf verfügbaren Produkten.
    Verwendet Google Gemini AI für realistische, sinnvolle Rezepte.
    """
    if not produkte_liste or len(produkte_liste) == 0:
        return None

    # Extrahiere nur die Produktnamen
    produkt_namen = [p["name"] for p in produkte_liste]
    zutaten_text = ", ".join(produkt_namen)

    # Prüfe ob API Key verfügbar ist
    if not GEMINI_API_KEY or GEMINI_API_KEY == "HIER_DEINEN_API_KEY_EINTRAGEN":
        return {
            "title": "⚠️ API Key fehlt",
            "description": "Um KI-generierte Rezepte zu erhalten, muss ein GEMINI_API_KEY in der config.py Datei eingetragen werden.",
            "ingredients": produkt_namen,
            "steps": [
                "1. Öffne die Datei 'config.py' im Hauptverzeichnis",
                "2. Besuche https://aistudio.google.com/app/apikey",
                "3. Erstelle einen kostenlosen API Key",
                "4. Trage den API Key in config.py ein (Zeile 15)",
                "5. Starte die App neu",
            ],
            "time": "N/A",
            "servings": "N/A",
        }

    try:
        # Erstelle intelligenten Prompt für Gemini
        prompt = f"""Du bist ein kreativer Koch. Erstelle ein realistisches, kochbares Rezept mit folgenden Zutaten aus dem Kühlschrank:

{zutaten_text}

WICHTIG:
- Das Rezept MUSS zu den vorhandenen Zutaten passen (z.B. kein Salat mit Burger Buns)
- Verwende NUR Zutaten, die sinnvoll zusammenpassen
- Falls die Zutaten nicht für ein vollständiges Gericht reichen, schlage ein einfaches Gericht vor oder empfehle, was noch besorgt werden sollte
- Sei kreativ aber realistisch
- Erstelle ein Rezept nur aus den Zutaten, die bald ablaufen, und achte darauf, dass sie geschmacklich zusammenpassen und ein sinnvolles Gericht ergeben.
- Verwende nur Zutaten, die geschmacklich gut zusammenpassen, und lasse alle anderen weg. Versuche nicht, alles auf einmal zu verwenden.
- Nutze herrkömliche Gerichte und probiere nicht neuem Sachen zu erfinden und probiere nicht alles in Rezept zu quetschen. Richte dich aber bei der Auswahl der Produkte an das Ablaufdatum
- Es sollen keine Verrückten Kombinationen sein

Antworte im folgenden JSON-Format (ohne Markdown, nur pures JSON):
{{
  "title": "Rezeptname",
  "description": "Kurze appetitliche Beschreibung (1-2 Sätze)",
  "ingredients": ["Zutat 1", "Zutat 2", "Zutat 3"],
  "steps": ["Schritt 1", "Schritt 2", "Schritt 3"],
  "time": "ca. 20 Minuten",
  "servings": "2 Personen"
}}"""

        # Generiere mit Gemini
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        # Parse JSON Response
        response_text = response.text.strip()

        # Entferne Markdown Code-Blöcke falls vorhanden
        if response_text.startswith("```"):
            # Entferne ```json oder ``` am Anfang
            response_text = (
                response_text.split("\n", 1)[1]
                if "\n" in response_text
                else response_text[3:]
            )
            # Entferne ``` am Ende
            if response_text.endswith("```"):
                response_text = response_text[:-3]

        rezept = json.loads(response_text)
        return rezept

    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Response text: {response_text}")
        return {
            "title": "Kreatives Kühlschrank-Gericht",
            "description": "Ein improvisiertes Gericht mit deinen Zutaten",
            "ingredients": produkt_namen,
            "steps": [
                "Die Zutaten waschen und vorbereiten",
                "Kombiniere die Zutaten kreativ",
                "Mit Gewürzen abschmecken",
                "Servieren und genießen",
            ],
            "time": "ca. 25 Minuten",
            "servings": "2 Personen",
        }
    except Exception as e:
        print(f"Fehler bei Rezeptgenerierung: {e}")
        return {
            "title": "⚠️ Fehler bei der Generierung",
            "description": f"Fehler: {str(e)}",
            "ingredients": produkt_namen,
            "steps": ["Bitte versuche es erneut"],
            "time": "N/A",
            "servings": "N/A",
        }


# ------------------ PRODUKTNAME über Barcode ------------------
def get_produktname(barcode):
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("product", {}).get("product_name", "").strip()
    except:
        pass
    return None


# ------------------ ROUTE ------------------
@app.route("/", methods=["GET", "POST"])
def index():
    global users

    # LOGIN
    if "user" not in session:
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            if username in users and users[username] == password:
                session["user"] = username
                if username not in produkte:
                    produkte[username] = []
                    speichere_produkte(produkte)
                return redirect(url_for("index"))
            else:
                error = "Falscher Login"
        return render_template("index.html", login=True, error=error)

    # BENUTZER EINGELOGGT
    user = session["user"]
    if user not in produkte:
        produkte[user] = []

    dev_mode = user == "admin"  # Admin kann Benutzer bearbeiten

    # ADMIN-FUNKTION: Benutzer hinzufügen/löschen
    if dev_mode and request.method == "POST":
        if "add_user" in request.form:
            new_user = request.form.get("new_user").strip()
            new_pass = request.form.get("new_pass").strip()
            if new_user and new_pass:
                users[new_user] = new_pass
                speichere_users(users)
        elif "delete_user" in request.form:
            del_user = request.form.get("delete_user")
            if del_user in users and del_user != "admin":
                users.pop(del_user)
                speichere_users(users)

    # PRODUKT-HANDLING
    if request.method == "POST" and not request.form.get("username"):
        if "add" in request.form:
            barcode = request.form.get("barcode", "").strip()
            manual_name = request.form.get("manual_name", "").strip()
            ablauf = request.form.get("ablauf", "").strip()
            if manual_name:
                name = manual_name
            elif barcode:
                name = get_produktname(barcode) or f"Unbekanntes Produkt ({barcode})"
            else:
                name = "Unbekanntes Produkt"
            produkte[user].append({"name": name, "ablauf": ablauf})
            speichere_produkte(produkte)

        elif "delete" in request.form:
            index_to_delete = int(request.form.get("delete"))
            if 0 <= index_to_delete < len(produkte[user]):
                produkte[user].pop(index_to_delete)
                speichere_produkte(produkte)

        elif "edit" in request.form:
            index_to_edit = int(request.form.get("edit_index"))
            neuer_name = request.form.get("edit_name", "").strip()
            if 0 <= index_to_edit < len(produkte[user]) and neuer_name:
                produkte[user][index_to_edit]["name"] = neuer_name
                speichere_produkte(produkte)

        return redirect(url_for("index"))

    # PRODUKTSUCHE
    suchbegriff = request.args.get("suche", "").strip().lower()
    gefiltert = produkte[user]
    if suchbegriff:
        gefiltert = [p for p in produkte[user] if suchbegriff in p["name"].lower()]

    return render_template(
        "index.html",
        produkte=gefiltert,
        user=user,
        login=False,
        dev_mode=dev_mode,
        users=users,
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


@app.route("/api/change-password", methods=["POST"])
def change_password():
    """API Endpunkt zum Ändern des Passworts"""
    if "user" not in session:
        return jsonify({"success": False, "message": "Nicht eingeloggt"}), 401

    user = session["user"]
    data = request.get_json()
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Bitte alle Felder ausfüllen"})

    if users.get(user) != current_password:
        return jsonify({"success": False, "message": "Aktuelles Passwort ist falsch"})

    if len(new_password) < 3:
        return jsonify(
            {"success": False, "message": "Neues Passwort muss mindestens 3 Zeichen lang sein"}
        )

    users[user] = new_password
    speichere_users(users)
    return jsonify({"success": True, "message": "Passwort erfolgreich geändert"})


@app.route("/api/generate-recipe")
def api_generate_recipe():
    """API Endpunkt zum Generieren von Rezepten basierend auf Benutzerprodukten"""
    global rezepte
    if "user" not in session:
        return jsonify({"success": False, "message": "Nicht eingeloggt"}), 401

    user = session["user"]
    if user not in produkte or len(produkte[user]) == 0:
        return jsonify(
            {
                "success": False,
                "message": "Du hast noch keine Produkte in deinem Kühlschrank! Füge erst einige Produkte hinzu.",
            }
        )

    rezept = generiere_rezept(produkte[user])

    if rezept:
        # Speichere Rezept in History
        if user not in rezepte:
            rezepte[user] = []

        # Füge Metadaten hinzu
        rezept_mit_meta = {
            "id": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "is_favorite": False,
            "recipe": rezept,
        }

        rezepte[user].insert(0, rezept_mit_meta)  # Neuestes zuerst
        speichere_rezepte(rezepte)

        return jsonify({"success": True, "recipe": rezept, "recipe_id": rezept_mit_meta["id"]})
    else:
        return jsonify(
            {
                "success": False,
                "message": "Rezeptgenerierung fehlgeschlagen. Bitte versuche es erneut.",
            }
        )


@app.route("/api/recipe-history")
def api_recipe_history():
    """API Endpunkt zum Abrufen der Rezept-History"""
    global rezepte
    if "user" not in session:
        return jsonify({"success": False, "message": "Nicht eingeloggt"}), 401

    user = session["user"]
    if user not in rezepte:
        rezepte[user] = []

    # Bereinige alte Rezepte
    rezepte[user] = bereinige_alte_rezepte(rezepte[user])
    speichere_rezepte(rezepte)

    return jsonify({"success": True, "recipes": rezepte[user]})


@app.route("/api/toggle-favorite", methods=["POST"])
def api_toggle_favorite():
    """API Endpunkt zum Favorisieren/Unfavorisieren eines Rezepts"""
    global rezepte
    if "user" not in session:
        return jsonify({"success": False, "message": "Nicht eingeloggt"}), 401

    user = session["user"]
    data = request.get_json()
    recipe_id = data.get("recipe_id")

    if not recipe_id:
        return jsonify({"success": False, "message": "Rezept ID fehlt"})

    if user not in rezepte:
        return jsonify({"success": False, "message": "Keine Rezepte gefunden"})

    # Finde und toggle Favorit
    for rezept in rezepte[user]:
        if rezept["id"] == recipe_id:
            rezept["is_favorite"] = not rezept.get("is_favorite", False)
            speichere_rezepte(rezepte)
            return jsonify({"success": True, "is_favorite": rezept["is_favorite"]})

    return jsonify({"success": False, "message": "Rezept nicht gefunden"})


# ------------------ MAIN ------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
