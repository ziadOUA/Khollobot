import discord
from discord import app_commands
import pandas as pd
import os
import asyncio
import json
import datetime
from discord.ext import tasks


global colles
global groups
global data

with open("data.json", "r") as f:
    data = json.load(f)

bot = discord.Client(intents=discord.Intents.all())
tree = app_commands.CommandTree(bot)

colles = {}
groups = []
group = {}


def semaine_actuelle():
    return abs(datetime.date.today().isocalendar()[1] - 38)


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
    df1 = pd.read_excel("collomètre.xlsx", sheet_name=0)
    data_colles = df1.to_dict(orient="records")

    df2 = pd.read_excel("collomètre.xlsx", sheet_name=1)
    data_groups = df2.to_dict(orient="records")

    global colles, groups
    colles = {}
    groups = []

    current_matiere = None

    # Traiter les colles (de df1)
    for row in data_colles:
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
                    if key_semaine not in colles:
                        colles[key_semaine] = []
                    colles[key_semaine].append({
                        "group_id": group_id,
                        "matiere": current_matiere,
                        "colleur": colleur,
                        "jour": jour,
                        "heure": heure,
                        "semaine": semaine_from_key
                    })

    # Traiter les groupes (de df2)
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
    return groups, colles


def kholles_semaines(user_id: int, semaine: int = None) -> dict:
    user_data = data["Members"][str(user_id)]
    user_group_id = user_data["group_id"]

    user_colles = []
    for kholle in colles[f"S_{semaine_actuelle() if not semaine else semaine}"]:
        if kholle["group_id"] == user_group_id:
            user_colles.append(kholle)
    user_colles = sorted(user_colles, key=lambda x: day_to_num[x["jour"]])
    return user_colles


@bot.event
async def on_ready():
    get_kholles()
    bot.add_view(Select_group())
    # send_dm.start()
    # send_dm_reminder.start()
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
        url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")
    embed.set_footer(text="MP2I >>>> MPSI")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="connection", description="Relie ton compte discord aux colles")
async def connect(interaction: discord.Integration):
    if str(interaction.user.id) in data["Members"]:
        data["Members"][interaction.user.id] = {}
        with open("data.json", "w") as f:
            json.dump(data, f, indent=4)

    embed = discord.Embed(
        title="Dans quel groupe es-tu ?",
        description="Choisis ton groupe dans la liste ci-dessous.",
        colour=discord.Colour.purple()
    )
    embed.set_footer(text="MP2I >>>> MPSI")
    embed.set_thumbnail(
        url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

    await interaction.response.send_message(embed=embed, view=Select_group(), ephemeral=True)


@tree.command(name="mescolles", description="Affiche tes colles prévues pour cette semaine")
async def colles_cmd(interaction: discord.Integration):
    member = None
    for m in data["Members"]:
        if m == str(interaction.user.id):
            member = m
            break
    if not member:
        embed = discord.Embed(
            title="Erreur",
            description="Tu n'as pas encore relié ton compte Discord, ou n'as pas fini ta connexion. Utilise la commande /connection.",
            colour=discord.Colour.purple()
        )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    user_colles = kholles_semaines(interaction.user.id)

    if not user_colles:
        embed = discord.Embed(
            title="Aucune colle cette semaine",
            description="Tu n'as pas de colles prévues pour cette semaine.",
            colour=discord.Colour.green()
        )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Tes colles pour la semaine",
        description=f"Voici les colles que tu as pour la S_{semaine_actuelle()} (Semaine {semaine_actuelle() + 38}) : ",
        colour=discord.Colour.purple()
    )
    for kholle in user_colles:
        embed.add_field(
            name=f"{kholle['matiere']} avec {kholle['colleur']}",
            value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
        )
    embed.set_footer(text="MP2I >>>> MPSI")
    embed.set_thumbnail(
        url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

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
                title="Aucune colle cette semaine",
                description="Tu n'as pas de colles prévues pour cette semaine.",
                colour=discord.Colour.green()
            )
            embed.set_footer(text="MP2I >>>> MPSI")
            embed.set_thumbnail(
                url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        user_colles = kholles_semaines(
            interaction.user.id, semaine=self.semaine)

        embed = discord.Embed(
            title=f"Tes colles pour la semaine",
            description=f"Voici les colles que tu as pour la S_{self.semaine} (Semaine {self.semaine + 38}) : ",
            colour=discord.Colour.purple()
        )
        for kholle in user_colles:
            embed.add_field(
                name=f"{kholle['matiere']} avec {kholle['colleur']}",
                value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
            )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")
        view = select_week()
        view.semaine = self.semaine
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Semaine suivante", style=discord.ButtonStyle.success, emoji="➡️")
    async def first_button_callback(self, interaction, button):
        self.semaine += 1

        try:
            user_colles = kholles_semaines(
                interaction.user.id, semaine=self.semaine)
        except:
            embed = discord.Embed(
                title="Aucune colle cette semaine",
                description="Tu n'as pas de colles prévues pour cette semaine.",
                colour=discord.Colour.green()
            )
            embed.set_footer(text="MP2I >>>> MPSI")
            embed.set_thumbnail(
                url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

            await interaction.response.edit_message(embed=embed, view=None)
            return

        embed = discord.Embed(
            title=f"Tes colles pour la semaine",
            description=f"Voici les colles que tu as pour la S_{self.semaine} (Semaine {self.semaine + 38}) : ",
            colour=discord.Colour.purple()
        )
        for kholle in user_colles:
            embed.add_field(
                name=f"{kholle['matiere']} avec {kholle['colleur']}",
                value=f"```\nLe {kholle['jour']} à {kholle['heure']}```",
            )
        embed.set_footer(text="MP2I >>>> MPSI")
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")
        view = select_week()
        view.semaine = self.semaine
        await interaction.response.edit_message(embed=embed, view=view)


# @tasks.loop(hours=168)
# async def send_dm():
#     for member in data["Members"]:
#         for kholle in colles[f"S_{semaine_actuelle()}"]:
#             if kholle["group_id"] == data["Members"][str(member)]["group_id"]:
#                 user = await bot.fetch_user(data["Members"][member]["discord_id"])
#                 embed = discord.Embed(
#                     title="Rappel de ta khôlle",
#                     description=f"Tu as une khôlle de {kholle['matiere']} avec {kholle['colleur']} le {kholle['jour']} à {kholle['heure']}.",
#                     colour=discord.Colour.purple()
#                 )
#                 embed.set_footer(text="MP2I >>>> MPSI")
#                 embed.set_thumbnail(
#                     url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

#                 await user.send(embed=embed)


# @send_dm.before_loop
# async def before():
#     await bot.wait_until_ready()
#     next_run = datetime.datetime.combine(
#         datetime.date.today() + datetime.timedelta((3 - datetime.date.today().weekday()) % 7),
#         datetime.time(8, 0)
#     )
#     await asyncio.sleep((next_run - datetime.datetime.now()).total_seconds())


# @tasks.loop(hours=72)
# async def send_dm_reminder():
#     for member in data["Members"]:
#         for kholle in colles[f"S_{semaine_actuelle()}"]:
#             if kholle["group_id"] == data["Members"][member]["group_id"] and kholle["semaine"] == semaine_actuelle():
#                 if datetime.datetime.now().weekday() != day_to_num[kholle["jour"]]-3:
#                     continue
#                 if not data["Members"][member].get("reminder", True):
#                     continue
#                 user = await bot.fetch_user(data["Members"][member]["discord_id"])
#                 embed = discord.Embed(
#                     title="Rappel de ta khôlle dans 3 jours",
#                     description=f"Tu as une khôlle de {kholle['matiere']} avec {kholle['colleur']} le {kholle['jour']} à {kholle['heure']}.",
#                     colour=discord.Colour.purple()
#                 )
#                 embed.set_footer(text="MP2I >>>> MPSI")
#                 embed.set_thumbnail(
#                     url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")
#                 await user.send(embed=embed)


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
            url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

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
            url="https://cdn.discordapp.com/icons/883070060070064148/c1880648a1ab2805d254c47a14e9053c.png?size=256&amp;aquality=lossless")

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
            description="Tu recevras un rappel avant ta khôlle." if choice else "Tu ne recevras pas de rappel.",
            colour=discord.Colour.purple()
        )
        await interaction.response.edit_message(embed=embed, view=None)


bot.run(open("token.txt").read().strip())
