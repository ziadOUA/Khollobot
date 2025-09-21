import discord
from discord import app_commands
import pandas as pd
import json
import datetime
from discord.ext import tasks
from ics import Calendar, Event

with open("data.json", "r") as f:
    data = json.load(f)

with open("config.json") as f:
    config = json.load(f)

with open("Zone-B.ics", 'r') as f:
    zoneB = Calendar(f.read())

bot = discord.Client(intents=discord.Intents.all())
tree = app_commands.CommandTree(bot)

url = "https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless"
groups = []
khôlles = {}
semaine_collometre = {}


def semaine_S():
    """Donne le dictionnaire de correspondance sur le colomètre ou None si elle n'y est pas"""
    holidays = []

    # Année de début de la periode scolaire, à changer chaque année
    year = config["CurrentYear"]
    for event in zoneB.events:
        date = event.begin.datetime.replace(tzinfo=None)
        if ("Vacances" in event.name) and (datetime.datetime(year, 9, 1) <= date < datetime.datetime(year + 1, 8, 25)):
            # La 1ere semaine de chaque vacance (+1 parce que le début c'est le vendredi) (+1 parce que ce module de ### commence l'année à la semaine 0)
            holidays.append(int(event.begin.datetime.strftime('%W'))+2)
            holidays.append(int(event.end.datetime.strftime('%W')))
    # Semaine de début des khôlles, à changer chaque semestre
    week = config["FirstColleWeek"]
    nb = 0
    while nb <= 15:  # Nombre de semaine de khôlles
        if not ((week) in holidays):
            semaine_collometre[nb] = week
            nb += 1
        week += 1
        if week > int(datetime.datetime(year, 12, 31).strftime('%W')):
            week = 1


def semaine_actuelle():
    """Fonction renvoyant le numéro de la semaine de travail, ou la prochaine il n'y a pas cours cette semaine

    >>> semaine_actuelle()
    3
    """
    if (datetime.date.today().isocalendar()[1]) in semaine_collometre.values():
        return list(semaine_collometre.values()).index(datetime.date.today().isocalendar()[1])


day_to_num = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6  # why not ecoute
}


def get_kholles():
    """Func that reads the collomètre and returns a tuple of (group, khôlles)
    TODO Make it also tell which group as what half group classes
    """
    df1 = pd.read_excel("collomètre.xlsx", sheet_name=0)
    data_khôlles = df1.to_dict(orient="records")

    df2 = pd.read_excel("collomètre.xlsx", sheet_name=1)
    data_groups = df2.to_dict(orient="records")

    current_matiere = None

    # Use the first page to get the khôlles
    for row in data_khôlles:
        if pd.notna(row['Matière']) and pd.isna(row['Colleur']):
            # Ignore the half-class groups
            if "Groupes demi-classe" in row['Matière']:
                current_matiere = None
                continue
            current_matiere = row['Matière']
            continue

        if pd.notna(row['Colleur']) and current_matiere:
            colleur = row['Colleur']
            jour = row['Jour'] if pd.notna(row['Jour']) else None
            heure = row['Heure'] if pd.notna(row['Heure']) else None

            for semaine in range(16):
                col_name = f'S{semaine}'
                if pd.notna(row[col_name]):
                    group_id = int(row[col_name]) if isinstance(
                        row[col_name], (int, float)) else row[col_name]

                    key = f"{group_id}_S{semaine}"

                    semaine_from_key = int(key.split("_S")[-1])
                    key_semaine = "S_" + str(semaine_from_key)
                    if key_semaine not in khôlles:
                        khôlles[key_semaine] = []
                    khôlles[key_semaine].append({
                        "group_id": group_id,
                        "matiere": current_matiere,
                        "colleur": colleur,
                        "jour": jour,
                        "heure": heure,
                        "semaine": semaine_from_key
                    })

    # Use the second page to get the groups
    for row in data_groups[2:]:
        if pd.notna(row['Unnamed: 0']):
            group_a = {
                "group_id": int(row['Unnamed: 0']),
                "membres": []
            }
            for col in ['Unnamed: 1', 'Unnamed: 2', 'Unnamed: 3']:
                if pd.notna(row[col]):
                    group_a["membres"].append(row[col])
            groups.append(group_a)

        if pd.notna(row['Unnamed: 4']):
            group_b = {
                "group_id": int(row['Unnamed: 4']),
                "membres": []
            }
            for col in ['Unnamed: 5', 'Unnamed: 6', 'Unnamed: 7']:
                if pd.notna(row[col]):
                    group_b["membres"].append(row[col])
            groups.append(group_b)
    return groups, khôlles


def kholles_semaines(user_id: int, semaine: int = None) -> dict:
    """
    Sends the week's khôlles for a user_id
    If semaine is not given use the current week"""
    user_data = data["Members"][str(user_id)]
    user_group_id = user_data["group_id"]

    user_khôlles = []
    for kholle in khôlles[f"S_{semaine_actuelle() if not semaine else semaine}"]:
        if kholle["group_id"] == user_group_id:
            user_khôlles.append(kholle)
    user_khôlles = sorted(user_khôlles, key=lambda x: day_to_num[x["jour"]])
    return user_khôlles


@bot.event
async def on_ready():
    get_kholles()
    semaine_S()
    await send_reminder_saturday()
    await send_reminder_2days_before()
    print(f'We have logged in as {bot.user}')
    await tree.sync(guild=None)


@tree.command(name="information", description="Quelques infos sur le bot")
async def info(interaction: discord.Integration):
    embed = discord.Embed(
        title="Informations",
        description="Voici diverses informations sur le bot"
    )
    embed.add_field(name="Vos données", value="Vos données sont stockés dans un fichier qui n'est pas publique, si vous voulez la supression de vos donneés demandez a l'administrateur du programme")
    embed.add_field(name="Le bot", value="Ce bot a été crée pour donner les kholes de la mp2i de Thiers, il est opensource, son code source est sur https://github.com/LeRatGondin/Khollobot")
    embed.set_thumbnail(
        url=url)
    embed.set_footer(text="MP2I >>>> MPSI")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="connection", description="Relie ton compte discord aux khôlles")
async def connect(interaction: discord.Integration):
    if str(interaction.user.id) in data["Members"]:
        data["Members"][str(interaction.user.id)] = {}
        with open("data.json", "w") as f:
            json.dump(data, f, indent=4)

    embed = discord.Embed(
        title="Dans quel groupe es-tu ?",
        description="Choisis ton groupe dans la liste ci-dessous.",
        colour=discord.Colour.purple()
    )
    embed.set_footer(text="MP2I >>>> MPSI")
    embed.set_thumbnail(
        url=url)

    await interaction.response.send_message(embed=embed, view=Select_group(), ephemeral=True)


@tree.command(name="mescolles", description="Affiche tes khôlles prévues pour cette semaine")
async def khôlles_cmd(interaction: discord.Integration):
    member = data["Members"].get(str(interaction.user.id))

    if not member:
        embed = discord.Embed(
            title="Erreur",
            description="Tu n'as pas encore relié ton compte Discord, ou n'as pas fini ta connexion. Utilise la commande /connection.",
            colour=discord.Colour.purple()
        )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    user_khôlles = kholles_semaines(interaction.user.id)

    if not user_khôlles:
        embed = discord.Embed(
            title="Aucune khôlle cette semaine",
            description="Tu n'as pas de khôlles prévues pour cette semaine.",
            colour=discord.Colour.green()
        )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Tes khôlles pour la semaine",
        description=f"Salut, {data["Members"][str(interaction.user.id)]["name"].split(" ")[1]}, voici les khôlles que tu as pour la S_{semaine_actuelle()} (Semaine {datetime.date.today().isocalendar()[1]} de l'année) : ",
        colour=discord.Colour.purple()
    )
    for kholle in user_khôlles:
        embed.add_field(
            name=f"{kholle['matiere']} avec {kholle['colleur']}",
            value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
        )
    embed.set_footer(text="MP2I >>>> MPSI")
    embed.set_thumbnail(
        url=url)

    await interaction.response.send_message(embed=embed, ephemeral=True, view=select_week())


class select_week(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.semaine = semaine_actuelle()

    @discord.ui.button(label="Semaine precedente", style=discord.ButtonStyle.danger, emoji="⬅️")
    async def second_button_callback(self, interaction, button):
        self.semaine -= 1

        if self.semaine < 0:
            embed = discord.Embed(
                title="Aucune khôlle cette semaine",
                description="Tu n'as pas de khôlles prévues pour cette semaine.",
                colour=discord.Colour.green()
            )
            embed.set_footer(text="MP2I >>>> MPSI")
            embed.set_thumbnail(
                url=url)

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        user_khôlles = kholles_semaines(
            interaction.user.id, semaine=self.semaine)

        embed = discord.Embed(
            title=f"Tes khôlles pour la semaine",
            description=f"Voici les khôlles que tu as pour la S_{self.semaine} (Semaine {semaine_collometre[self.semaine]} de l'année) : ",
            colour=discord.Colour.purple()
        )
        for kholle in user_khôlles:
            embed.add_field(
                name=f"{kholle['matiere']} avec {kholle['colleur']}",
                value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
            )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)
        view = select_week()
        view.semaine = self.semaine
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Semaine suivante", style=discord.ButtonStyle.success, emoji="➡️")
    async def next_week_button_callback(self, interaction, button):
        """
        Button handler to show next week khôlles
        """
        self.semaine += 1

        try:
            user_khôlles = kholles_semaines(
                interaction.user.id, semaine=self.semaine)
        except:
            embed = discord.Embed(
                title="Aucune khôlle cette semaine",
                description="Tu n'as pas de khôlles prévues pour cette semaine.",
                colour=discord.Colour.green()
            )
            embed.set_footer(text="MP2I >>>> MPSI")
            embed.set_thumbnail(
                url=url)

            await interaction.response.edit_message(embed=embed, view=None)
            return

        embed = discord.Embed(
            title=f"Tes khôlles pour la semaine",
            description=f"Salut {data["Members"][str(interaction.user.id)]["name"].split(" ")[1]}, voici les khôlles que tu as pour la S_{self.semaine} (Semaine {semaine_collometre[self.semaine]} de l'année) : ",
            colour=discord.Colour.purple()
        )
        for kholle in user_khôlles:
            embed.add_field(
                name=f"{kholle['matiere']} avec {kholle['colleur']}",
                value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
            )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)
        view = select_week()
        view.semaine = self.semaine
        await interaction.response.edit_message(embed=embed, view=view)


async def send_reminder_saturday():
    # Send a remainder every saturday for next week khôlles
    if not (datetime.date.today().timetuple().tm_wday == 5):
        return
    for member in data["Members"]:
        if data["Members"][member]["reminder"] != "True":
            return
        user = await bot.fetch_user(member)
        user_khôlles = kholles_semaines(member, semaine_actuelle()+1)

        embed = discord.Embed(
            title=f"Tes khôlles pour la semaine",
            description=f"Salut {data["Members"][member]["name"].split(" ")[1]}, voici les khôlles que tu as pour la S_{semaine_actuelle()+1} (Semaine {semaine_collometre[semaine_actuelle()+1]}) : ",
            colour=discord.Colour.purple()
        )
        for kholle in user_khôlles:
            embed.add_field(
                name=f"{kholle['matiere']} avec {kholle['colleur']}",
                value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
            )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)

        # To send dms, the app needs to be a bot, not just an app.
        await user.send(embed=embed)


async def send_reminder_2days_before():
    for member in data["Members"]:
        if data["Members"][member]["reminder"] != "True":
            return
        user = await bot.fetch_user(member)
        user_khôlles = kholles_semaines(member, semaine_actuelle()+1)

        embed = discord.Embed(
            title=f"Rappel de ta khôlle",
            description=f"Salut {data["Members"][member]["name"].split(" ")[1]}, voici la khôlle que tu as pour dans après demain, prépare la bien ! : ",
            colour=discord.Colour.red()
        )
        for kholle in user_khôlles:
            if day_to_num[kholle['jour']] - datetime.date.today().timetuple().tm_wday == 2:
                embed.add_field(
                    name=f"{kholle['matiere']} avec {kholle['colleur']}",
                    value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
                )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)
        if embed.fields == []:
            continue
        # To send dms, the app needs to be a bot, not just an app.
        await user.send(embed=embed)


class Select_group(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelectGroupDropdown())


class SelectGroupDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"Groupe {group['group_id']} : {', '.join(group['membres'])}",
                value=str(group["group_id"])
            )
            for group in groups
        ]
        super().__init__(
            placeholder="Choisis ton groupe dans la liste",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_group"
        )

    async def callback(self, interaction: discord.Interaction):
        group_id = int(self.values[0])
        selected_group = next(
            (g for g in groups if g["group_id"] == group_id), None)

        embed = discord.Embed(
            title="Qui es-tu ?",
            description=f"Tu es dans le groupe {group_id}. Choisis ton nom dans la liste ci-dessous.",
            colour=discord.Colour.purple()
        )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)

        await interaction.response.edit_message(embed=embed, view=Select_member(selected_group))


class Select_member(discord.ui.View):
    def __init__(self, group):
        super().__init__(timeout=None)
        self.add_item(SelectMemberDropdown(group))


class SelectMemberDropdown(discord.ui.Select):
    def __init__(self, group):
        options = [
            discord.SelectOption(
                label=member,
                value=member
            ) for member in group["membres"]
        ]
        super().__init__(
            placeholder="Choisis ton nom",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_member"
        )
        self.group = group

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        embed = discord.Embed(
            title="C'est noté !",
            description=f"Tu es donc {member}, membre du groupe {self.group['group_id']} !",
            colour=discord.Colour.purple()
        )
        data["Members"][str(interaction.user.id)] = {
            "name": member,
            "group_id": self.group["group_id"]
        }
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)

        with open("data.json", "w") as f:
            json.dump(data, f, indent=4)
        await interaction.response.edit_message(embed=embed, view=ReminderChoiceView(interaction.user.id))


class ReminderChoiceView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.select(
        placeholder="Souhaites-tu recevoir un rappel de ta khôlle ?",
        options=[
            discord.SelectOption(label="Oui", value=True),
            discord.SelectOption(label="Non", value=False)
        ],
        custom_id="reminder_choice"
    )
    async def select_callback(self, interaction, select):
        choice = select.values[0]
        data["Members"][str(self.user_id)]["reminder"] = choice
        with open("data.json", "w") as f:
            json.dump(data, f, indent=4)
        embed = discord.Embed(
            title="Préférence enregistrée",
            description="Tu recevras un rappel avant ta khôlle." if choice == "True" else "Tu ne recevras pas de rappel avant ta khôlle.",
            colour=discord.Colour.purple()
        )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url=url)
        await interaction.response.edit_message(embed=embed, view=None)


bot.run(open("token.txt").read().strip())
