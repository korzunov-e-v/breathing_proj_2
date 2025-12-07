from flask import redirect, render_template_string, request, session

from admin.admin_app import create_admin_app


app = create_admin_app()

# Простая страница логина по TG ID
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
        input, button { width: 100%; padding: 10px; margin: 10px 0; }
        button { background: #007cba; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <h2>Admin Login</h2>
    <form method="post">
        <input type="number" name="tg_id" placeholder="Enter your Telegram ID" required>
        <button type="submit">Login</button>
    </form>
    {% if error %}
        <p style="color: red;">{{ error }}</p>
    {% endif %}
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    from admin.views import ADMIN_IDS

    if request.method == "POST":
        try:
            tg_id = int(request.form.get("tg_id"))
            if tg_id in ADMIN_IDS:
                session["tg_id"] = tg_id
                return redirect("/admin")
            else:
                return render_template_string(LOGIN_PAGE, error="Access denied")
        except (ValueError, TypeError):
            return render_template_string(LOGIN_PAGE, error="Invalid Telegram ID")

    return render_template_string(LOGIN_PAGE)


@app.route("/")
def home():
    return redirect("/admin")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
