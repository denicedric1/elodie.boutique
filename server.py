from flask import Flask, jsonify, render_template, request, session, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

app.secret_key = "elodie-boutique-cle-secrete-2026"

DATABASE = "boutique.db"


# =========================================================
# BASE DE DONNÉES
# =========================================================

def creer_base_de_donnees():

    connexion = sqlite3.connect(DATABASE)
    curseur = connexion.cursor()

    curseur.execute("""
        CREATE TABLE IF NOT EXISTS commandes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            numero_commande TEXT UNIQUE NOT NULL,

            nom_client TEXT NOT NULL,

            telephone TEXT NOT NULL,

            ville TEXT NOT NULL,

            commune TEXT NOT NULL,

            quartier TEXT NOT NULL,

            adresse TEXT NOT NULL,

            produits TEXT NOT NULL,

            total REAL NOT NULL,

            statut TEXT NOT NULL DEFAULT 'Commande reçue',

            livreur TEXT,

            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)

    curseur.execute("""
        CREATE TABLE IF NOT EXISTS utilisateurs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nom TEXT NOT NULL,

            identifiant TEXT UNIQUE NOT NULL,

            mot_de_passe TEXT NOT NULL,

            role TEXT NOT NULL,

            actif INTEGER NOT NULL DEFAULT 1,

            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)

    connexion.commit()
    connexion.close()


# =========================================================
# COMPTES
# =========================================================

def creer_comptes():

    connexion = sqlite3.connect(DATABASE)
    curseur = connexion.cursor()

    comptes = [

        (
            "Administrateur",
            "admin",
            "admin123",
            "admin"
        ),

        (
            "Assistance",
            "assistance",
            "assist123",
            "assistance"
        ),

        (
            "Kouassi Jean",
            "kouassi",
            "kouassi123",
            "livreur"
        ),

        (
            "Yao Michel",
            "yao",
            "yao123",
            "livreur"
        ),

        (
            "Koffi Serge",
            "koffi",
            "koffi123",
            "livreur"
        )

    ]

    # ---------------------------------------------------------
    # Créer les comptes s'ils n'existent pas
    # ---------------------------------------------------------

    for compte in comptes:

        curseur.execute("""
            INSERT OR IGNORE INTO utilisateurs (
                nom,
                identifiant,
                mot_de_passe,
                role,
                actif
            )
            VALUES (?, ?, ?, ?, 1)
        """, compte)

    # ---------------------------------------------------------
    # Réactiver les 3 livreurs officiels
    # ---------------------------------------------------------

    curseur.execute("""
        UPDATE utilisateurs
        SET actif = 1,
            nom = 'Kouassi Jean',
            role = 'livreur'
        WHERE identifiant = 'kouassi'
    """)

    curseur.execute("""
        UPDATE utilisateurs
        SET actif = 1,
            nom = 'Yao Michel',
            role = 'livreur'
        WHERE identifiant = 'yao'
    """)

    curseur.execute("""
        UPDATE utilisateurs
        SET actif = 1,
            nom = 'Koffi Serge',
            role = 'livreur'
        WHERE identifiant = 'koffi'
    """)

    # ---------------------------------------------------------
    # Désactiver les anciens comptes livreurs
    #
    # IMPORTANT :
    # On ne supprime rien de la base.
    # Les anciennes commandes restent donc conservées.
    # ---------------------------------------------------------

    curseur.execute("""
        UPDATE utilisateurs
        SET actif = 0
        WHERE role = 'livreur'
        AND identifiant NOT IN (
            'kouassi',
            'yao',
            'koffi'
        )
    """)

    connexion.commit()
    connexion.close()


creer_base_de_donnees()
creer_comptes()


# =========================================================
# ACCUEIL
# =========================================================

@app.route("/")
def accueil():

    return render_template("index.html")


# =========================================================
# PAGE DE CONNEXION
# =========================================================

@app.route("/login")
def login():

    return render_template("login.html")


# =========================================================
# PAGE COMMANDE CLIENT
# =========================================================

@app.route("/commande")
def page_commande():

    return render_template("commande.html")


# =========================================================
# CONNEXION
# =========================================================

@app.route("/connexion", methods=["POST"])
def connexion():

    donnees = request.get_json()

    if not donnees:

        return jsonify({
            "success": False,
            "message": "Aucune donnée reçue."
        }), 400

    role = donnees.get("role")
    identifiant = donnees.get("identifiant")
    mot_de_passe = donnees.get("mot_de_passe")

    connexion_db = sqlite3.connect(DATABASE)

    connexion_db.row_factory = sqlite3.Row

    curseur = connexion_db.cursor()

    curseur.execute("""
        SELECT *
        FROM utilisateurs
        WHERE identifiant = ?
        AND mot_de_passe = ?
        AND role = ?
        AND actif = 1
    """, (
        identifiant,
        mot_de_passe,
        role
    ))

    utilisateur = curseur.fetchone()

    connexion_db.close()

    if not utilisateur:

        return jsonify({
            "success": False,
            "message":
                "Identifiant ou mot de passe incorrect."
        })

    session["utilisateur_id"] = utilisateur["id"]

    session["nom"] = utilisateur["nom"]

    session["identifiant"] = utilisateur["identifiant"]

    session["role"] = utilisateur["role"]

    if role == "admin":

        destination = "/admin"

    elif role == "assistance":

        destination = "/assistance"

    else:

        destination = "/livreur"

    return jsonify({
        "success": True,
        "redirect": destination
    })


# =========================================================
# ADMIN
# =========================================================

@app.route("/admin")
def admin():

    if "utilisateur_id" not in session:

        return redirect("/login")

    if session.get("role") != "admin":

        return "Accès refusé", 403

    return render_template("admin.html")


# =========================================================
# ASSISTANCE
# =========================================================

@app.route("/assistance")
def assistance():

    if "utilisateur_id" not in session:

        return redirect("/login")

    if session.get("role") != "assistance":

        return "Accès refusé", 403

    return render_template("assistance.html")


# =========================================================
# LIVREUR
# =========================================================

@app.route("/livreur")
def livreur():

    if "utilisateur_id" not in session:

        return redirect("/login")

    if session.get("role") != "livreur":

        return "Accès refusé", 403

    return render_template("livreur.html")


# =========================================================
# DÉCONNEXION
# =========================================================

@app.route("/deconnexion")
def deconnexion():

    session.clear()

    return redirect("/login")


# =========================================================
# CRÉER UNE COMMANDE CLIENT
# =========================================================

@app.route("/api/creer-commande", methods=["POST"])
def creer_commande():

    try:

        donnees = request.get_json()

        if not donnees:

            return jsonify({
                "success": False,
                "message": "Aucune donnée reçue."
            }), 400

        nom = donnees.get("nom")
        telephone = donnees.get("telephone")
        ville = donnees.get("ville")
        commune = donnees.get("commune")
        quartier = donnees.get("quartier")
        adresse = donnees.get("adresse")
        produits = donnees.get("produits")
        total = donnees.get("total")

        if not all([
            nom,
            telephone,
            ville,
            commune,
            quartier,
            adresse,
            produits
        ]):

            return jsonify({
                "success": False,
                "message":
                    "Veuillez remplir tous les champs."
            }), 400

        if total is None:

            return jsonify({
                "success": False,
                "message":
                    "Le total de la commande est manquant."
            }), 400

        connexion = sqlite3.connect(DATABASE)
        curseur = connexion.cursor()

        date_actuelle = datetime.now().strftime("%Y%m%d")

        curseur.execute("""
            SELECT COUNT(*)
            FROM commandes
            WHERE numero_commande LIKE ?
        """, (
            "ELD-" + date_actuelle + "-%",
        ))

        nombre_commandes = curseur.fetchone()[0] + 1

        numero_commande = (
            "ELD-"
            + date_actuelle
            + "-"
            + str(nombre_commandes).zfill(4)
        )

        curseur.execute("""
            INSERT INTO commandes (
                numero_commande,
                nom_client,
                telephone,
                ville,
                commune,
                quartier,
                adresse,
                produits,
                total,
                statut
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            numero_commande,
            nom,
            telephone,
            ville,
            commune,
            quartier,
            adresse,
            produits,
            float(total),
            "Commande reçue"
        ))

        connexion.commit()
        connexion.close()

        return jsonify({

            "success": True,

            "message":
                "Commande créée avec succès !",

            "numero_commande":
                numero_commande

        })

    except Exception as erreur:

        print(
            "ERREUR CREATION COMMANDE :",
            erreur
        )

        return jsonify({

            "success": False,

            "message":
                "Erreur serveur : "
                + str(erreur)

        }), 500


# =========================================================
# LISTE DES COMMANDES
# =========================================================

@app.route("/api/commandes")
def api_commandes():

    if "utilisateur_id" not in session:

        return jsonify({
            "message":
                "Vous devez être connecté."
        }), 401

    connexion = sqlite3.connect(DATABASE)

    connexion.row_factory = sqlite3.Row

    curseur = connexion.cursor()

    if session.get("role") == "livreur":

        curseur.execute("""
            SELECT *
            FROM commandes
            WHERE livreur = ?
            ORDER BY id DESC
        """, (
            session.get("nom"),
        ))

    else:

        curseur.execute("""
            SELECT *
            FROM commandes
            ORDER BY id DESC
        """)

    commandes = curseur.fetchall()

    connexion.close()

    return jsonify([
        dict(commande)
        for commande in commandes
    ])


# =========================================================
# LISTE DES LIVREURS
# =========================================================

@app.route("/api/livreurs")
def api_livreurs():

    if "utilisateur_id" not in session:

        return jsonify({
            "message":
                "Vous devez être connecté."
        }), 401

    if session.get("role") not in ["admin", "assistance"]:

        return jsonify({
            "message":
                "Accès refusé."
        }), 403

    connexion = sqlite3.connect(DATABASE)

    connexion.row_factory = sqlite3.Row

    curseur = connexion.cursor()

    # ---------------------------------------------------------
    # SEULS LES 3 LIVREURS OFFICIELS SONT AFFICHÉS
    # ---------------------------------------------------------

    curseur.execute("""
        SELECT id, nom, identifiant
        FROM utilisateurs
        WHERE role = 'livreur'
        AND actif = 1
        AND identifiant IN (
            'kouassi',
            'yao',
            'koffi'
        )
        ORDER BY nom ASC
    """)

    livreurs = curseur.fetchall()

    connexion.close()

    return jsonify([
        dict(livreur)
        for livreur in livreurs
    ])


# =========================================================
# VALIDER UNE COMMANDE - ADMIN
# =========================================================

@app.route(
    "/admin/valider/<int:commande_id>",
    methods=["POST"]
)
def valider_commande(commande_id):

    if "utilisateur_id" not in session:

        return jsonify({
            "message":
                "Vous devez être connecté."
        }), 401

    if session.get("role") != "admin":

        return jsonify({
            "message":
                "Accès refusé."
        }), 403

    connexion = sqlite3.connect(DATABASE)

    curseur = connexion.cursor()

    curseur.execute("""
        UPDATE commandes
        SET statut = ?
        WHERE id = ?
    """, (
        "Commande validée",
        commande_id
    ))

    connexion.commit()

    connexion.close()

    return jsonify({
        "success": True,
        "message":
            "Commande validée avec succès"
    })


# =========================================================
# ATTRIBUER UN LIVREUR - ASSISTANCE
# =========================================================

@app.route(
    "/assistance/attribuer/<int:commande_id>",
    methods=["POST"]
)
def attribuer_livreur(commande_id):

    if "utilisateur_id" not in session:

        return jsonify({
            "message":
                "Vous devez être connecté."
        }), 401

    if session.get("role") != "assistance":

        return jsonify({
            "message":
                "Accès refusé."
        }), 403

    donnees = request.get_json()

    if not donnees:

        return jsonify({
            "message":
                "Aucune donnée reçue."
        }), 400

    nom_livreur = donnees.get("livreur")

    if not nom_livreur:

        return jsonify({
            "message":
                "Veuillez choisir un livreur."
        }), 400

    connexion = sqlite3.connect(DATABASE)

    curseur = connexion.cursor()

    curseur.execute("""
        SELECT id
        FROM utilisateurs
        WHERE nom = ?
        AND role = 'livreur'
        AND actif = 1
    """, (
        nom_livreur,
    ))

    if not curseur.fetchone():

        connexion.close()

        return jsonify({
            "message":
                "Ce livreur n'existe pas ou n'est pas actif."
        }), 400

    curseur.execute("""
        UPDATE commandes
        SET livreur = ?,
            statut = ?
        WHERE id = ?
    """, (
        nom_livreur,
        "Livreur attribué",
        commande_id
    ))

    connexion.commit()

    if curseur.rowcount == 0:

        connexion.close()

        return jsonify({
            "message":
                "Commande introuvable."
        }), 404

    connexion.close()

    return jsonify({
        "success": True,
        "message":
            "Livreur attribué avec succès."
    })


# =========================================================
# RÉATTRIBUER UN LIVREUR - ADMIN
# =========================================================

@app.route(
    "/admin/attribuer/<int:commande_id>",
    methods=["POST"]
)
def admin_attribuer_livreur(commande_id):

    if "utilisateur_id" not in session:

        return jsonify({
            "message":
                "Vous devez être connecté."
        }), 401

    if session.get("role") != "admin":

        return jsonify({
            "message":
                "Accès refusé."
        }), 403

    donnees = request.get_json()

    if not donnees:

        return jsonify({
            "message":
                "Aucune donnée reçue."
        }), 400

    nom_livreur = donnees.get("livreur")

    if not nom_livreur:

        return jsonify({
            "message":
                "Veuillez choisir un livreur."
        }), 400

    connexion = sqlite3.connect(DATABASE)

    curseur = connexion.cursor()

    # ---------------------------------------------------------
    # VÉRIFICATION DU LIVREUR
    # ---------------------------------------------------------

    curseur.execute("""
        SELECT id
        FROM utilisateurs
        WHERE nom = ?
        AND role = 'livreur'
        AND actif = 1
    """, (
        nom_livreur,
    ))

    livreur_existe = curseur.fetchone()

    if not livreur_existe:

        connexion.close()

        return jsonify({
            "success": False,
            "message":
                "Ce livreur n'existe pas ou n'est pas actif."
        }), 400

    # ---------------------------------------------------------
    # RÉATTRIBUTION
    # ---------------------------------------------------------

    curseur.execute("""
        UPDATE commandes
        SET livreur = ?,
            statut = ?
        WHERE id = ?
    """, (
        nom_livreur,
        "Livreur attribué",
        commande_id
    ))

    connexion.commit()

    if curseur.rowcount == 0:

        connexion.close()

        return jsonify({
            "success": False,
            "message":
                "Commande introuvable."
        }), 404

    connexion.close()

    return jsonify({
        "success": True,
        "message":
            "Commande réattribuée avec succès."
    })


# =========================================================
# CHANGER LE STATUT - ADMIN
# =========================================================

@app.route(
    "/admin/statut/<int:commande_id>",
    methods=["POST"]
)
def changer_statut_admin(commande_id):

    if "utilisateur_id" not in session:

        return jsonify({
            "message":
                "Vous devez être connecté."
        }), 401

    if session.get("role") != "admin":

        return jsonify({
            "message":
                "Accès refusé."
        }), 403

    donnees = request.get_json()

    if not donnees:

        return jsonify({
            "success": False,
            "message":
                "Aucune donnée reçue."
        }), 400

    nouveau_statut = donnees.get("statut")

    statuts_autorises = [

        "Commande reçue",

        "Commande validée",

        "Livreur attribué",

        "Colis récupéré",

        "En route vers le client",

        "Livraison en cours",

        "Commande livrée"

    ]

    if nouveau_statut not in statuts_autorises:

        return jsonify({

            "success": False,

            "message":
                "Statut invalide."

        }), 400

    connexion = sqlite3.connect(DATABASE)

    curseur = connexion.cursor()

    curseur.execute("""
        UPDATE commandes
        SET statut = ?
        WHERE id = ?
    """, (
        nouveau_statut,
        commande_id
    ))

    connexion.commit()

    if curseur.rowcount == 0:

        connexion.close()

        return jsonify({

            "success": False,

            "message":
                "Commande introuvable."

        }), 404

    connexion.close()

    return jsonify({

        "success": True,

        "message":
            "Statut de la commande mis à jour avec succès."

    })


# =========================================================
# CHANGER LE STATUT - LIVREUR
# =========================================================

@app.route(
    "/livreur/statut/<int:commande_id>",
    methods=["POST"]
)
def changer_statut_livreur(commande_id):

    if "utilisateur_id" not in session:

        return jsonify({
            "message":
                "Vous devez être connecté."
        }), 401

    if session.get("role") != "livreur":

        return jsonify({
            "message":
                "Accès refusé."
        }), 403

    donnees = request.get_json()

    if not donnees:

        return jsonify({
            "success": False,
            "message":
                "Aucune donnée reçue."
        }), 400

    nouveau_statut = donnees.get("statut")

    statuts_autorises = [

        "Colis récupéré",

        "En route vers le client",

        "Livraison en cours",

        "Commande livrée"

    ]

    if nouveau_statut not in statuts_autorises:

        return jsonify({

            "success": False,

            "message":
                "Statut invalide."

        }), 400

    connexion = sqlite3.connect(DATABASE)

    curseur = connexion.cursor()

    curseur.execute("""
        UPDATE commandes
        SET statut = ?
        WHERE id = ?
        AND livreur = ?
    """, (
        nouveau_statut,
        commande_id,
        session.get("nom")
    ))

    connexion.commit()

    if curseur.rowcount == 0:

        connexion.close()

        return jsonify({

            "success": False,

            "message":
                "Commande introuvable ou non attribuée à ce livreur."

        }), 404

    connexion.close()

    return jsonify({

        "success": True,

        "message":
            "Statut mis à jour avec succès."

    })


# =========================================================
# SUIVI CLIENT
# =========================================================

@app.route("/suivi")
def suivi():

    return render_template("suivi.html")


# =========================================================
# LANCEMENT DU SERVEUR
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)
