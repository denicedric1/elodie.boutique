from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
from functools import wraps

from dotenv import load_dotenv
from supabase import create_client, Client


# ==========================================================
# AFFICHAGE SÉCURISÉ DES ERREURS (console Windows)
# ==========================================================
# Sur certains systèmes Windows, afficher un message d'erreur
# contenant des caractères spéciaux (emoji, accents rares...)
# peut faire planter tout le serveur avec une OSError. Cette
# fonction affiche toujours quelque chose, sans jamais planter.

def log_erreur(message, erreur=None):

    try:

        if erreur is not None:

            print(message, erreur)

        else:

            print(message)

    except OSError:

        texte_erreur = (
            str(erreur)
            .encode("ascii", errors="replace")
            .decode("ascii")
            if erreur is not None
            else ""
        )

        print(
            message,
            texte_erreur,
            "(certains caractères n'ont pas pu être affichés)"
        )


# ==========================================================
# CONFIGURATION
# ==========================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL est absent du fichier .env")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY est absent du fichier .env")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_KEY est absent du fichier .env "
        "(nécessaire pour le tableau de bord administrateur)"
    )


# Client "normal" : utilisé pour l'authentification des utilisateurs
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# Client "admin" : utilisé uniquement côté serveur pour lire/modifier
# tous les profils, sans être limité par les règles de sécurité (RLS).
# Ne JAMAIS exposer ce client ou cette clé au navigateur.
supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


# ==========================================================
# URL DE NOTRE APPLICATION
# ==========================================================

APP_URL = "http://127.0.0.1:5000"


# ==========================================================
# OUTILS : RÔLES ET PROFILS
# ==========================================================

def get_profile(user_id):
    """Récupère le profil (dont le rôle) d'un utilisateur."""

    try:

        response = (
            supabase_admin
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )

        return response.data

    except Exception as e:

        log_erreur("Erreur récupération profil :", e)

        return None


def role_required(*roles_autorises):
    """
    Décorateur pour protéger une route selon le rôle.
    Exemple : @role_required("admin")
    """

    def decorateur(fonction):

        @wraps(fonction)
        def fonction_protegee(*args, **kwargs):

            if not session.get("user_id"):

                return redirect(
                    url_for("connexion")
                )

            role_utilisateur = session.get(
                "user_role",
                "client"
            )

            if role_utilisateur not in roles_autorises:

                return render_template(
                    "acces-refuse.html"
                ), 403

            return fonction(*args, **kwargs)

        return fonction_protegee

    return decorateur


# ==========================================================
# PRODUITS (stockés dans Supabase, table "produits")
# ==========================================================

def get_tous_les_produits():
    """Récupère tous les produits depuis Supabase."""

    try:

        response = (
            supabase
            .table("produits")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return response.data

    except Exception as e:

        log_erreur("Erreur récupération produits :", e)

        return []


def get_produit_par_id(produit_id):
    """Récupère un seul produit depuis Supabase, via son id."""

    try:

        response = (
            supabase
            .table("produits")
            .select("*")
            .eq("id", produit_id)
            .single()
            .execute()
        )

        return response.data

    except Exception as e:

        log_erreur("Erreur récupération produit :", e)

        return None


def get_produits_populaires(limite=8):
    """
    Produits populaires : ceux marqués manuellement 'force_populaire'
    apparaissent en priorité, puis on complète avec les plus consultés.
    """

    try:

        response = (
            supabase
            .table("produits")
            .select("*")
            .order("force_populaire", desc=True)
            .order("vues", desc=True)
            .limit(limite)
            .execute()
        )

        return response.data

    except Exception as e:

        log_erreur("Erreur produits populaires :", e)

        return []


def get_nouveautes(limite=8):
    """
    Nouveautés : celles marquées manuellement 'force_nouveau'
    apparaissent en priorité, puis on complète par date d'ajout.
    """

    try:

        response = (
            supabase
            .table("produits")
            .select("*")
            .order("force_nouveau", desc=True)
            .order("created_at", desc=True)
            .limit(limite)
            .execute()
        )

        return response.data

    except Exception as e:

        log_erreur("Erreur nouveautés :", e)

        return []


def get_promotions_actives(limite=8):
    """Produits ayant un prix promotionnel défini."""

    try:

        response = (
            supabase
            .table("produits")
            .select("*")
            .not_.is_("prix_promo", "null")
            .order("created_at", desc=True)
            .limit(limite)
            .execute()
        )

        return response.data

    except Exception as e:

        log_erreur("Erreur promotions :", e)

        return []


def get_categories_avec_compte():
    """Liste des catégories avec le nombre réel de produits chacune."""

    try:

        tous_les_produits = get_tous_les_produits()

        compteur = {}

        for produit in tous_les_produits:

            categorie = (
                produit.get("categorie")
                or "Autres"
            )

            compteur[categorie] = (
                compteur.get(categorie, 0) + 1
            )

        return [
            {"nom": nom, "nombre": nombre}
            for nom, nombre in compteur.items()
        ]

    except Exception as e:

        log_erreur("Erreur comptage catégories :", e)

        return []


def incrementer_vues(produit_id, vues_actuelles):
    """Ajoute 1 au compteur de vues d'un produit."""

    try:

        supabase_admin.table("produits").update(
            {
                "vues": (vues_actuelles or 0) + 1
            }
        ).eq(
            "id",
            produit_id
        ).execute()

    except Exception as e:

        log_erreur("Erreur incrémentation vues :", e)


# ==========================================================
# FICHE PRODUIT
# ==========================================================

@app.route("/produit/<produit_id>")
def fiche_produit(produit_id):

    produit = get_produit_par_id(produit_id)

    if not produit:

        return redirect(
            url_for("produits")
        )

    incrementer_vues(
        produit_id,
        produit.get("vues", 0)
    )

    favoris = session.get(
        "favoris",
        []
    )

    favoris_noms = [
        p["nom"]
        for p in favoris
    ]

    return render_template(
        "produit-detail.html",
        produit=produit,
        favoris_noms=favoris_noms
    )


# ==========================================================
# API : SUGGESTIONS DE RECHERCHE (utilisée par l'accueil)
# ==========================================================

@app.route("/api/recherche-suggestions")
def api_recherche_suggestions():

    recherche = request.args.get("q", "").strip().lower()

    if not recherche or len(recherche) < 2:

        return jsonify([])

    tous_les_produits = get_tous_les_produits()

    correspondances = [
        {
            "id": produit["id"],
            "nom": produit["nom"],
            "prix": produit["prix"],
            "categorie": produit.get("categorie")
        }
        for produit in tous_les_produits
        if recherche in produit["nom"].lower()
    ]

    return jsonify(correspondances[:6])


# ==========================================================
# ACCUEIL
# ==========================================================

@app.route("/")
def index():

    tous_les_produits = get_tous_les_produits()

    produits_vedette = tous_les_produits[:10]

    produits_populaires = get_produits_populaires(8)
    nouveautes = get_nouveautes(8)
    promotions_accueil = get_promotions_actives(8)
    categories_avec_compte = get_categories_avec_compte()

    favoris = session.get(
        "favoris",
        []
    )

    favoris_noms = [
        produit["nom"]
        for produit in favoris
    ]

    return render_template(
        "index.html",
        produits=produits_vedette,
        produits_populaires=produits_populaires,
        nouveautes=nouveautes,
        promotions_accueil=promotions_accueil,
        categories_avec_compte=categories_avec_compte,
        favoris_noms=favoris_noms
    )


# ==========================================================
# CATÉGORIES
# ==========================================================

@app.route("/categories")
def categories():

    return render_template(
        "categories.html"
    )


# ==========================================================
# PRODUITS + RECHERCHE
# ==========================================================

@app.route("/produits")
def produits():

    recherche = request.args.get(
        "q",
        ""
    ).strip()

    categorie_filtre = request.args.get(
        "categorie",
        ""
    ).strip()

    tous_les_produits = get_tous_les_produits()

    if categorie_filtre:

        produits_filtres = [
            produit
            for produit in tous_les_produits
            if (produit.get("categorie") or "").lower()
            == categorie_filtre.lower()
        ]

    elif recherche:

        recherche_minuscule = recherche.lower()

        produits_filtres = []

        for produit in tous_les_produits:

            nom = (produit.get("nom") or "").lower()
            description = (produit.get("description") or "").lower()

            if (
                recherche_minuscule in nom
                or recherche_minuscule in description
            ):

                produits_filtres.append(
                    produit
                )

    else:

        produits_filtres = tous_les_produits

    favoris = session.get(
        "favoris",
        []
    )

    favoris_noms = [
        produit["nom"]
        for produit in favoris
    ]

    return render_template(
        "produits.html",
        produits=produits_filtres,
        favoris_noms=favoris_noms,
        recherche=recherche or categorie_filtre
    )


# ==========================================================
# PROMOTIONS
# ==========================================================

@app.route("/promotions")
def promotions():

    return render_template(
        "promotions.html"
    )


# ==========================================================
# LIVRAISON
# ==========================================================

@app.route("/livraison")
def livraison():

    return render_template(
        "livraison.html"
    )


# ==========================================================
# DEVENIR VENDEUR
# ==========================================================

@app.route(
    "/devenir-vendeur",
    methods=["GET", "POST"]
)
def devenir_vendeur():

    message = ""
    succes = False

    if request.method == "POST":

        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip().lower()
        telephone = request.form.get("telephone", "").strip()
        nom_boutique = request.form.get("nom_boutique", "").strip()
        description = request.form.get("description", "").strip()

        if not nom or not email or not nom_boutique:

            message = (
                "Veuillez remplir au moins votre nom, "
                "votre e-mail et le nom de votre boutique."
            )

        else:

            try:

                supabase.table("demandes_vendeur").insert(
                    {
                        "nom": nom,
                        "email": email,
                        "telephone": telephone,
                        "nom_boutique": nom_boutique,
                        "description": description
                    }
                ).execute()

                succes = True

            except Exception as e:

                log_erreur(
                    "Erreur candidature vendeur :",
                    e
                )

                message = (
                    "Une erreur est survenue lors de l'envoi "
                    "de votre candidature. Veuillez réessayer."
                )

    return render_template(
        "devenir-vendeur.html",
        message=message,
        succes=succes
    )


# ==========================================================
# INSCRIPTION SUPABASE
# ==========================================================

@app.route(
    "/inscription",
    methods=["GET", "POST"]
)
def inscription():

    message = ""

    if request.method == "POST":

        nom = request.form.get(
            "nom",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not nom or not email or not password:

            message = (
                "Veuillez remplir tous les champs."
            )

            return render_template(
                "inscription.html",
                message=message
            )

        if len(password) < 6:

            message = (
                "Le mot de passe doit contenir "
                "au moins 6 caractères."
            )

            return render_template(
                "inscription.html",
                message=message
            )

        try:

            response = supabase.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "nom": nom
                        },
                        "email_redirect_to": APP_URL
                    }
                }
            )

            if response.user:

                # Création automatique du profil (rôle "client" par défaut)
                try:

                    supabase_admin.table("profiles").insert(
                        {
                            "id": response.user.id,
                            "nom": nom,
                            "email": email,
                            "role": "client"
                        }
                    ).execute()

                except Exception as e:

                    log_erreur(
                        "Erreur création profil :",
                        e
)

                return render_template(
                    "connexion.html",
                    message=(
                        "Votre compte a été créé avec succès. "
                        "Un e-mail de confirmation vient "
                        "d'être envoyé à votre adresse. "
                        "Veuillez confirmer votre e-mail "
                        "avant de vous connecter."
                    )
                )

            message = (
                "Impossible de créer le compte."
            )

        except Exception as e:

            log_erreur(
                "Erreur Supabase inscription :",
                e
)

            message = (
                "Une erreur est survenue lors "
                "de la création du compte."
            )

    return render_template(
        "inscription.html",
        message=message
    )


# ==========================================================
# CONNEXION SUPABASE
# ==========================================================

@app.route(
    "/connexion",
    methods=["GET", "POST"]
)
def connexion():

    message = ""

    if request.args.get(
        "confirmation"
    ) == "success":

        message = (
            "Votre adresse e-mail a été confirmée. "
            "Vous pouvez maintenant vous connecter."
        )

    if request.args.get(
        "reinitialisation"
    ) == "success":

        message = (
            "Votre mot de passe a été réinitialisé. "
            "Vous pouvez maintenant vous connecter."
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            message = (
                "Veuillez remplir tous les champs."
            )

            return render_template(
                "connexion.html",
                message=message
            )

        try:

            response = supabase.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password
                }
            )

            if response.user:

                user = response.user

                session["user_id"] = user.id

                session["user_email"] = (
                    user.email
                )

                metadata = (
                    user.user_metadata
                    or {}
                )

                session["user_name"] = (
                    metadata.get(
                        "nom",
                        user.email
                    )
                )

                # Récupération du rôle depuis la table profiles
                profil = get_profile(user.id)

                role = (
                    profil["role"]
                    if profil
                    else "client"
                )

                session["user_role"] = role

                # Redirection selon le rôle de l'utilisateur
                if role == "admin":

                    return redirect(
                        url_for("admin_dashboard")
                    )

                elif role == "assistant":

                    return redirect(
                        url_for("assistant_dashboard")
                    )

                elif role == "livreur":

                    return redirect(
                        url_for("livreur_dashboard")
                    )

                return redirect(
                    url_for("index")
                )

            message = (
                "Impossible de vous connecter."
            )

        except Exception as e:

            log_erreur(
                "Erreur Supabase connexion :",
                e
)

            erreur = str(e).lower()

            if (
                "email not confirmed"
                in erreur
            ):

                message = (
                    "Votre adresse e-mail n'est "
                    "pas encore confirmée. "
                    "Veuillez consulter votre "
                    "boîte e-mail."
                )

            elif (
                "invalid login credentials"
                in erreur
            ):

                message = (
                    "Adresse e-mail ou "
                    "mot de passe incorrect."
                )

            else:

                message = (
                    "Adresse e-mail ou "
                    "mot de passe incorrect."
                )

    return render_template(
        "connexion.html",
        message=message
    )


# ==========================================================
# CALLBACK CONFIRMATION E-MAIL
# ==========================================================

@app.route("/auth/callback")
def auth_callback():

    return redirect(
        url_for(
            "connexion",
            confirmation="success"
        )
    )


# ==========================================================
# DÉCONNEXION
# ==========================================================

@app.route("/deconnexion")
def deconnexion():

    try:

        supabase.auth.sign_out()

    except Exception as e:

        log_erreur(
            "Erreur Supabase déconnexion :",
            e
)

    session.clear()

    return redirect(
        url_for("index")
    )


# ==========================================================
# MOT DE PASSE OUBLIÉ
# ==========================================================

@app.route(
    "/mot-de-passe-oublie",
    methods=["GET", "POST"]
)
def mot_de_passe_oublie():

    message = ""

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if not email:

            message = (
                "Veuillez indiquer votre "
                "adresse e-mail."
            )

            return render_template(
                "mot-de-passe-oublie.html",
                message=message
            )

        try:

            supabase.auth.reset_password_for_email(
                email,
                {
                    "redirect_to":
                        f"{APP_URL}/nouveau-mot-de-passe"
                }
            )

            message = (
                "Si un compte existe avec "
                "cette adresse e-mail, "
                "un lien de réinitialisation "
                "vient d'être envoyé."
            )

        except Exception as e:

            log_erreur(
                "Erreur Supabase mot de passe oublié :",
                e
)

            message = (
                "Si un compte existe avec "
                "cette adresse e-mail, "
                "un lien de réinitialisation "
                "vient d'être envoyé."
            )

    return render_template(
        "mot-de-passe-oublie.html",
        message=message
    )


# ==========================================================
# NOUVEAU MOT DE PASSE
# ==========================================================

@app.route(
    "/nouveau-mot-de-passe",
    methods=["GET", "POST"]
)
def nouveau_mot_de_passe():

    message = ""

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        password_confirmation = request.form.get(
            "password_confirmation",
            ""
        )

        if len(password) < 6:

            message = (
                "Le mot de passe doit contenir "
                "au moins 6 caractères."
            )

        elif password != password_confirmation:

            message = (
                "Les mots de passe "
                "ne correspondent pas."
            )

        else:

            try:

                response = supabase.auth.update_user(
                    {
                        "password": password
                    }
                )

                if response.user:

                    return redirect(
                        url_for(
                            "connexion",
                            reinitialisation="success"
                        )
                    )

                message = (
                    "Impossible de modifier "
                    "le mot de passe."
                )

            except Exception as e:

                log_erreur(
                    "Erreur changement mot de passe :",
                    e
)

                message = (
                    "Le lien de réinitialisation "
                    "est peut-être expiré ou invalide."
                )

    return render_template(
        "nouveau-mot-de-passe.html",
        message=message
    )


# ==========================================================
# ESPACE ADMINISTRATEUR
# ==========================================================

@app.route("/admin")
@role_required("admin")
def admin_dashboard():

    try:

        response = (
            supabase_admin
            .table("profiles")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        utilisateurs = response.data

    except Exception as e:

        log_erreur("Erreur chargement profils :", e)

        utilisateurs = []

    nombre_produits = len(
        get_tous_les_produits()
    )

    try:

        reponse_commandes = (
            supabase_admin
            .table("commandes")
            .select("id", count="exact")
            .execute()
        )

        nombre_commandes = reponse_commandes.count or 0

    except Exception as e:

        log_erreur("Erreur comptage commandes :", e)

        nombre_commandes = 0

    return render_template(
        "admin.html",
        utilisateurs=utilisateurs,
        nombre_produits=nombre_produits,
        nombre_commandes=nombre_commandes
    )


@app.route(
    "/admin/modifier-role/<user_id>",
    methods=["POST"]
)
@role_required("admin")
def admin_modifier_role(user_id):

    nouveau_role = request.form.get(
        "role",
        "client"
    )

    roles_valides = [
        "client",
        "admin",
        "assistant",
        "livreur"
    ]

    if nouveau_role not in roles_valides:

        return redirect(
            url_for("admin_dashboard")
        )

    try:

        supabase_admin.table("profiles").update(
            {
                "role": nouveau_role
            }
        ).eq(
            "id",
            user_id
        ).execute()

    except Exception as e:

        log_erreur(
            "Erreur modification rôle :",
            e
)

    return redirect(
        url_for("admin_dashboard")
    )


# ==========================================================
# ADMIN : GESTION DES PRODUITS
# ==========================================================

@app.route("/admin/produits")
@role_required("admin")
def admin_produits():

    produits_liste = get_tous_les_produits()

    return render_template(
        "admin-produits.html",
        produits=produits_liste
    )


@app.route(
    "/admin/produits/ajouter",
    methods=["GET", "POST"]
)
@role_required("admin")
def admin_ajouter_produit():

    message = ""

    if request.method == "POST":

        nom = request.form.get("nom", "").strip()
        description = request.form.get("description", "").strip()
        prix = request.form.get("prix", "0")
        image = request.form.get("image", "🛍️").strip()
        categorie = request.form.get("categorie", "").strip()
        stock = request.form.get("stock", "0")

        try:
            prix = int(prix)
        except ValueError:
            prix = 0

        try:
            stock = int(stock)
        except ValueError:
            stock = 0

        if not nom or prix <= 0:

            message = (
                "Veuillez indiquer au moins "
                "un nom et un prix valide."
            )

        else:

            try:

                supabase_admin.table("produits").insert(
                    {
                        "nom": nom,
                        "description": description,
                        "prix": prix,
                        "image": image or "🛍️",
                        "categorie": categorie,
                        "stock": stock
                    }
                ).execute()

                return redirect(
                    url_for("admin_produits")
                )

            except Exception as e:

                log_erreur("Erreur ajout produit :", e)

                message = (
                    "Une erreur est survenue "
                    "lors de l'ajout du produit."
                )

    return render_template(
        "admin-produit-form.html",
        message=message,
        produit=None
    )


@app.route(
    "/admin/produits/modifier/<produit_id>",
    methods=["GET", "POST"]
)
@role_required("admin")
def admin_modifier_produit(produit_id):

    message = ""

    try:

        response = (
            supabase_admin
            .table("produits")
            .select("*")
            .eq("id", produit_id)
            .single()
            .execute()
        )

        produit = response.data

    except Exception as e:

        log_erreur("Erreur chargement produit :", e)

        produit = None

    if not produit:

        return redirect(
            url_for("admin_produits")
        )

    if request.method == "POST":

        nom = request.form.get("nom", "").strip()
        description = request.form.get("description", "").strip()
        prix = request.form.get("prix", "0")
        image = request.form.get("image", "🛍️").strip()
        categorie = request.form.get("categorie", "").strip()
        stock = request.form.get("stock", "0")

        try:
            prix = int(prix)
        except ValueError:
            prix = 0

        try:
            stock = int(stock)
        except ValueError:
            stock = 0

        if not nom or prix <= 0:

            message = (
                "Veuillez indiquer au moins "
                "un nom et un prix valide."
            )

            produit.update(
                {
                    "nom": nom,
                    "description": description,
                    "prix": prix,
                    "image": image,
                    "categorie": categorie,
                    "stock": stock
                }
            )

        else:

            try:

                supabase_admin.table("produits").update(
                    {
                        "nom": nom,
                        "description": description,
                        "prix": prix,
                        "image": image or "🛍️",
                        "categorie": categorie,
                        "stock": stock
                    }
                ).eq(
                    "id",
                    produit_id
                ).execute()

                return redirect(
                    url_for("admin_produits")
                )

            except Exception as e:

                log_erreur("Erreur modification produit :", e)

                message = (
                    "Une erreur est survenue "
                    "lors de la modification."
                )

    return render_template(
        "admin-produit-form.html",
        message=message,
        produit=produit
    )


@app.route(
    "/admin/produits/supprimer/<produit_id>",
    methods=["POST"]
)
@role_required("admin")
def admin_supprimer_produit(produit_id):

    try:

        supabase_admin.table("produits").delete().eq(
            "id",
            produit_id
        ).execute()

    except Exception as e:

        log_erreur("Erreur suppression produit :", e)

    return redirect(
        url_for("admin_produits")
    )


@app.route(
    "/admin/produits/toggle-nouveau/<produit_id>",
    methods=["POST"]
)
@role_required("admin")
def admin_toggle_nouveau(produit_id):

    try:

        produit = (
            supabase_admin
            .table("produits")
            .select("force_nouveau")
            .eq("id", produit_id)
            .single()
            .execute()
        ).data

        nouvelle_valeur = not produit.get(
            "force_nouveau",
            False
        )

        supabase_admin.table("produits").update(
            {
                "force_nouveau": nouvelle_valeur
            }
        ).eq(
            "id",
            produit_id
        ).execute()

    except Exception as e:

        log_erreur(
            "Erreur bascule 'nouveau' :",
            e
        )

    return redirect(
        url_for("admin_produits")
    )


@app.route(
    "/admin/produits/toggle-populaire/<produit_id>",
    methods=["POST"]
)
@role_required("admin")
def admin_toggle_populaire(produit_id):

    try:

        produit = (
            supabase_admin
            .table("produits")
            .select("force_populaire")
            .eq("id", produit_id)
            .single()
            .execute()
        ).data

        nouvelle_valeur = not produit.get(
            "force_populaire",
            False
        )

        supabase_admin.table("produits").update(
            {
                "force_populaire": nouvelle_valeur
            }
        ).eq(
            "id",
            produit_id
        ).execute()

    except Exception as e:

        log_erreur(
            "Erreur bascule 'populaire' :",
            e
        )

    return redirect(
        url_for("admin_produits")
    )


# ==========================================================
# ESPACE ASSISTANT
# ==========================================================

@app.route("/assistant")
@role_required("admin", "assistant")
def assistant_dashboard():

    try:

        reponse = (
            supabase_admin
            .table("commandes")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )

        commandes_liste = reponse.data

    except Exception as e:

        log_erreur(
            "Erreur chargement commandes (assistant) :",
            e
        )

        commandes_liste = []

    return render_template(
        "assistant.html",
        commandes=commandes_liste
    )


# ==========================================================
# ESPACE LIVREUR
# ==========================================================

@app.route("/livreur")
@role_required("admin", "livreur")
def livreur_dashboard():

    try:

        reponse = (
            supabase_admin
            .table("commandes")
            .select("*")
            .in_("statut", ["confirmee", "preparation", "en_livraison"])
            .order("created_at", desc=True)
            .execute()
        )

        commandes_liste = reponse.data

    except Exception as e:

        log_erreur(
            "Erreur chargement commandes (livreur) :",
            e
        )

        commandes_liste = []

    return render_template(
        "livreur.html",
        commandes=commandes_liste
    )


# ==========================================================
# PANIER
# ==========================================================

@app.route(
    "/ajouter-au-panier",
    methods=["POST"]
)
def ajouter_au_panier():

    nom = request.form.get(
        "nom",
        ""
    ).strip()

    prix = request.form.get(
        "prix",
        "0"
    )

    image = request.form.get(
        "image",
        "🛍️"
    )

    try:

        prix = int(prix)

    except ValueError:

        prix = 0

    if "panier" not in session:

        session["panier"] = []

    panier = session["panier"]

    produit_existant = False

    for produit in panier:

        if produit["nom"] == nom:

            produit["quantite"] += 1

            produit_existant = True

            break

    if not produit_existant:

        panier.append(
            {
                "nom": nom,
                "prix": prix,
                "image": image,
                "quantite": 1
            }
        )

    session["panier"] = panier

    session.modified = True

    return redirect(
        url_for("panier")
    )


@app.route("/panier")
def panier():

    panier = session.get(
        "panier",
        []
    )

    total = sum(
        p["prix"] * p["quantite"]
        for p in panier
    )

    return render_template(
        "panier.html",
        panier=panier,
        total=total
    )


@app.route("/panier/plus/<int:index>")
def panier_plus(index):

    panier = session.get(
        "panier",
        []
    )

    if 0 <= index < len(panier):

        panier[index]["quantite"] += 1

    session["panier"] = panier
    session.modified = True

    return redirect(
        url_for("panier")
    )


@app.route("/panier/moins/<int:index>")
def panier_moins(index):

    panier = session.get(
        "panier",
        []
    )

    if 0 <= index < len(panier):

        panier[index]["quantite"] -= 1

        if panier[index]["quantite"] <= 0:

            panier.pop(index)

    session["panier"] = panier
    session.modified = True

    return redirect(
        url_for("panier")
    )


@app.route(
    "/supprimer-du-panier/<int:index>"
)
def supprimer_du_panier(index):

    panier = session.get(
        "panier",
        []
    )

    if 0 <= index < len(panier):

        panier.pop(index)

    session["panier"] = panier
    session.modified = True

    return redirect(
        url_for("panier")
    )


@app.route("/vider-panier")
def vider_panier():

    session["panier"] = []

    session.modified = True

    return redirect(
        url_for("panier")
    )


# ==========================================================
# COMMANDES
# ==========================================================

def calculer_frais_livraison(zone):

    if zone == "standard":
        return 1500

    if zone == "eloignee":
        return 2000

    return 0


@app.route(
    "/commande",
    methods=["GET", "POST"]
)
def commande():

    panier = session.get("panier", [])

    if not panier:

        return redirect(
            url_for("panier")
        )

    sous_total = sum(
        p["prix"] * p["quantite"]
        for p in panier
    )

    message = ""

    if request.method == "POST":

        nom = request.form.get("nom", "").strip()
        telephone = request.form.get("telephone", "").strip()
        email = request.form.get("email", "").strip()
        ville = request.form.get("ville", "").strip()
        commune = request.form.get("commune", "").strip()
        quartier = request.form.get("quartier", "").strip()
        adresse = request.form.get("adresse", "").strip()
        zone = request.form.get("zone_livraison", "")
        paiement = request.form.get("mode_paiement", "")

        champs_obligatoires = [
            nom, telephone, ville,
            commune, quartier, adresse,
            zone, paiement
        ]

        if not all(champs_obligatoires):

            message = (
                "Veuillez remplir tous les champs "
                "obligatoires avant de valider."
            )

        else:

            frais_livraison = calculer_frais_livraison(zone)
            total = sous_total + frais_livraison

            try:

                reponse = supabase.table("commandes").insert(
                    {
                        "user_id": session.get("user_id"),
                        "nom": nom,
                        "telephone": telephone,
                        "email": email or None,
                        "ville": ville,
                        "commune": commune,
                        "quartier": quartier,
                        "adresse": adresse,
                        "zone_livraison": zone,
                        "frais_livraison": frais_livraison,
                        "mode_paiement": paiement,
                        "sous_total": sous_total,
                        "total": total
                    }
                ).execute()

                nouvelle_commande = reponse.data[0]

                lignes = [
                    {
                        "commande_id": nouvelle_commande["id"],
                        "produit_id": p.get("id"),
                        "nom": p["nom"],
                        "prix": p["prix"],
                        "quantite": p["quantite"],
                        "image": p.get("image")
                    }
                    for p in panier
                ]

                supabase.table("commande_lignes").insert(
                    lignes
                ).execute()

                session["panier"] = []
                session.modified = True

                return redirect(
                    url_for(
                        "commande_confirmation",
                        numero=nouvelle_commande["numero"]
                    )
                )

            except Exception as e:

                log_erreur(
                    "Erreur création commande :",
                    e
                )

                message = (
                    "Une erreur est survenue lors de la "
                    "création de votre commande. Réessayez."
                )

    return render_template(
        "commande.html",
        panier=panier,
        sous_total=sous_total,
        message=message
    )


def get_commande_par_numero(numero):
    """Récupère une commande (et ses lignes) via son numéro."""

    try:

        reponse_commande = (
            supabase_admin
            .table("commandes")
            .select("*")
            .eq("numero", numero)
            .single()
            .execute()
        )

        commande_trouvee = reponse_commande.data

        if not commande_trouvee:
            return None, []

        reponse_lignes = (
            supabase_admin
            .table("commande_lignes")
            .select("*")
            .eq("commande_id", commande_trouvee["id"])
            .execute()
        )

        return commande_trouvee, reponse_lignes.data

    except Exception as e:

        log_erreur(
            "Erreur récupération commande :",
            e
        )

        return None, []


@app.route("/commande/confirmation/<numero>")
def commande_confirmation(numero):

    commande_trouvee, lignes = get_commande_par_numero(numero)

    if not commande_trouvee:

        return redirect(
            url_for("index")
        )

    return render_template(
        "commande_confirmee.html",
        commande=commande_trouvee,
        lignes=lignes
    )


@app.route("/commande/<numero>")
def commande_suivi(numero):

    commande_trouvee, lignes = get_commande_par_numero(
        numero.strip().upper()
    )

    return render_template(
        "commande-suivi.html",
        commande=commande_trouvee,
        lignes=lignes,
        numero_recherche=numero
    )


@app.route("/suivre-commande")
def suivre_commande():

    numero = request.args.get("numero", "").strip()

    if not numero:

        return redirect(
            url_for("index")
        )

    return redirect(
        url_for(
            "commande_suivi",
            numero=numero.upper()
        )
    )


# ==========================================================
# ADMIN : GESTION DES COMMANDES
# ==========================================================

@app.route("/admin/commandes")
@role_required("admin")
def admin_commandes():

    try:

        reponse = (
            supabase_admin
            .table("commandes")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        commandes_liste = reponse.data

    except Exception as e:

        log_erreur(
            "Erreur chargement commandes :",
            e
        )

        commandes_liste = []

    return render_template(
        "admin-commandes.html",
        commandes=commandes_liste
    )


@app.route(
    "/commande/statut/<commande_id>",
    methods=["POST"]
)
@role_required("admin", "livreur")
def modifier_statut_commande(commande_id):

    nouveau_statut = request.form.get("statut", "")

    statuts_valides = [
        "confirmee", "preparation",
        "en_livraison", "livree", "annulee"
    ]

    if nouveau_statut not in statuts_valides:

        return redirect(
            request.referrer or url_for("index")
        )

    try:

        supabase_admin.table("commandes").update(
            {
                "statut": nouveau_statut
            }
        ).eq(
            "id",
            commande_id
        ).execute()

    except Exception as e:

        log_erreur(
            "Erreur modification statut commande :",
            e
        )

    return redirect(
        request.referrer or url_for("index")
    )


# ==========================================================
# FAVORIS
# ==========================================================

@app.route(
    "/ajouter-favori",
    methods=["POST"]
)
def ajouter_favori():

    nom = request.form.get(
        "nom",
        ""
    ).strip()

    prix = request.form.get(
        "prix",
        "0"
    )

    image = request.form.get(
        "image",
        "🛍️"
    )

    try:

        prix = int(prix)

    except ValueError:

        prix = 0

    if not nom:

        return redirect(
            url_for("produits")
        )

    if "favoris" not in session:

        session["favoris"] = []

    favoris = session["favoris"]

    produit_existant = any(
        p["nom"] == nom
        for p in favoris
    )

    if not produit_existant:

        favoris.append(
            {
                "nom": nom,
                "prix": prix,
                "image": image
            }
        )

    session["favoris"] = favoris

    session.modified = True

    return redirect(
        url_for("produits")
    )


@app.route("/favoris")
def favoris():

    favoris = session.get(
        "favoris",
        []
    )

    return render_template(
        "favoris.html",
        favoris=favoris
    )


@app.route(
    "/supprimer-favori/<int:index>"
)
def supprimer_favori(index):

    favoris = session.get(
        "favoris",
        []
    )

    if 0 <= index < len(favoris):

        favoris.pop(index)

    session["favoris"] = favoris

    session.modified = True

    return redirect(
        url_for("favoris")
    )


# ==========================================================
# LANCEMENT DU SERVEUR
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
