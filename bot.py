import csv
import io
import json
import os
import time

import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

ROTATIONS_URL = "https://api.elitebot.dev/harvest-feast/rotations"
SHEET_URL = ("https://docs.google.com/spreadsheets/d/"
    "1nZI-4mNCymWb1pykwtnx--DnN_8NmEvSiDwwb9DGz8I/export?format=csv&gid=")
PESTS_URL = SHEET_URL + "1224099634"
# The sheet's own bazaar tab. Its Sell Price is the same instant-sell number
# Hypixel returns, and it is 877 bytes against 3.4 MB for the whole bazaar.
PRICES_URL = SHEET_URL + "0"

# crop -> pest, bazaar id, drop name, hourly cell, threshold cell, base coins/hr
# Cells are (row, column), zero indexed, read straight out of the sheet CSV.
# Mushroom has no drop or threshold because Slug is the benchmark the sheet
# measures everything else against.
# Base rates come from Elite's /rates screenshot and are unverified; Mushroom
# and Nether Wart are the two rows I could not tell apart.
CROPS = {
    "Wheat": ("Fly", "CORNUCOPIA", "Cornucopia", (11, 2), (28, 11), 27_527_133),
    "Potato": ("Locust", "DEEPFRIES", "Deepfries", (11, 5), (32, 11), 23_159_680),
    "Carrot": ("Cricket", "CARROT_ZEST", "Carrot Zest", (11, 8), (34, 11), 23_706_644),
    "Cactus": ("Mite", "CACTUS_FLOWER", "Cactus Flower", (11, 11), (37, 11), 22_010_905),
    "Melon": ("Earthworm", "MELON_JUICE", "Melon Juice", (11, 14), (38, 11), 28_007_526),
    "Moonflower": ("Firefly", "CRYSTALIZED_MOONLIGHT", "Crystalized Moonlight", (11, 17), (29, 11), 23_361_679),
    "Nether Wart": ("Beetle", "BOTROOT", "Botroot", (24, 2), (30, 11), 28_013_439),
    "Cocoa Beans": ("Moth", "DESIGNER_COFFEE_BEANS", "Designer Coffee Beans", (24, 8), (36, 11), 26_261_476),
    "Pumpkin": ("Rat", "AGGOURDIAN", "Aggourdian", (24, 11), (31, 11), 26_863_620),
    "Sugar Cane": ("Mosquito", "CANE_KNOT", "Cane Knot", (24, 14), (33, 11), 21_762_981),
    "Sunflower": ("Dragonfly", "SALTED_SUNFLOWER_SEEDS", "Salted Sunflower Seed", (24, 17), (39, 11), 22_494_213),
    "Wild Rose": ("Praying Mantis", "FLORAL_GELATIN", "Floral Gelatin", (37, 17), (35, 11), 23_159_001),
    "Mushroom": ("Slug", None, None, (25, 5), None, 27_878_609),
}

EMOJI = {
    "Wheat": "<:Wheat:1548208629629452350>",
    "Potato": "<:Potato:1548208624197705790>",
    "Carrot": "<:Carrot:1548208627192438834>",
    "Cactus": "<:Cactus:1548208617390608425>",
    "Melon": "<:Melon:1548208619579768862>",
    "Moonflower": "<:Moonflower:1548208697749282896>",
    "Nether Wart": "<:Nether_Wart:1548208632104226986>",
    "Cocoa Beans": "<:Cocoa_Beans:1548208634335330365>",
    "Pumpkin": "<:Pumpkin:1548208621672861747>",
    "Sugar Cane": "<:Sugar_Cane:1548208636705251378>",
    "Sunflower": "<:Sunflower:1548208695463378965>",
    "Wild Rose": "<:Wild_Rose:1548208692988743730>",
    "Mushroom": "<:Mushroom:1548208700244627516>",
    "Fly": "<:Fly:1548208735179251736>",
    "Locust": "<:Locust:1548208674139537409>",
    "Cricket": "<:Cricket:1548208677058650132>",
    "Mite": "<:Mite:1548208665079582770>",
    "Earthworm": "<:Earthworm:1548208667839701102>",
    "Firefly": "<:Firefly:1548208652371107950>",
    "Beetle": "<:Beetle:1548208658662424606>",
    "Moth": "<:Moth:1548208662974046279>",
    "Rat": "<:Rat:1548208672033738782>",
    "Mosquito": "<:Mosquito:1548208669836189767>",
    "Dragonfly": "<:Dragonfly:1548208656380858418>",
    "Praying Mantis": "<:Praying_Mantis:1548208644406124594>",
    "Slug": "<:Slug:1548208660826816595>",
    "Cornucopia": "<:Cornucopia:1548205921296056330>",
    "Deepfries": "<:Deepfries:1548205916849963049>",
    "Carrot Zest": "<:Carrot_Zest:1548205919396171866>",
    "Cactus Flower": "<:Cactus_Flower:1548205944926900294>",
    "Melon Juice": "<:Melon_Juice:1548205947690811442>",
    "Crystalized Moonlight": "<:Crystalized_Moonlight:1548205925217599513>",
    "Botroot": "<:Botroot:1548205930611609711>",
    "Designer Coffee Beans": "<:Designer_Coffee_Beans:1548205942934605884>",
    "Aggourdian": "<:Aggourdian:1548205954238124062>",
    "Cane Knot": "<:Cane_Knot:1548205951868342292>",
    "Salted Sunflower Seed": "<:Salted_Sunflower_Seeds:1548205927642038374>",
    "Floral Gelatin": "<:Floral_Gelatin:1548205923217051708>",

    "Ted's Contact Baked In Bread": "<:Contact:1548241320538275840>",
    "Finn's Focaccia": "<:Focaccia:1548241325755736124>",
    "Freshly Baked Heirloom": "<:Freshly_Baked_Heirloom:1548241328322641940>",
    "Freshly Baked Relic": "<:Freshly_Baked_Relic:1548241330055024702>",
    "Freshly Baked Artifact": "<:Freshly_Baked_Artifact:1548241333133639710>",
    "Freshly Baked Ring": "<:Freshly_Baked_Ring:1548241335452966932>",
    "Freshly Baked Talisman": "<:Freshly_Baked_Talisman:1548241337512366130>",
    "Feast 1 Book": "<:Feast:1548241322987618314>",
    "Scott's Contact Baked In Bread": "<:Contact:1548241320538275840>",
    "Feast Baker Scott": "<:Feast_Baker_Scott:1548241340007976971>"
}

client = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)
session = None


# ---------------------------------------------------------------- fetching

async def open_session():
    global session
    if session is None:
        session = aiohttp.ClientSession()
    return session


async def get_json(url):
    connection = await open_session()
    async with connection.get(url) as response:
        return await response.json()


async def get_csv(url):
    """Download a sheet tab and return it as a list of rows."""
    connection = await open_session()
    async with connection.get(url) as response:
        text = await response.text()
    return list(csv.reader(io.StringIO(text)))


# ---------------------------------------------------------------- reading data

def read_cell(sheet, cell):
    """Read one cell and turn its text into a number.

    The sheet writes numbers with thousands separators, like "25,344,568",
    so the commas have to come out before Python can read it as a number.
    """
    row_number, column_number = cell
    text = sheet[row_number][column_number]
    text = text.replace(",", "")
    return float(text)


def read_prices(rows):
    """Turn the price tab into {item id: sell price}.

    The tab has three columns: Item ID, Buy Price, Sell Price.
    Row 0 is the header, so it gets skipped.

    The sheet pulls these prices itself, so while it is refreshing a cell can
    come back blank. Google then exports that row with a column missing, or
    with text where a number should be. Either way the item is left out here
    and collect() copes with it being absent.
    """
    prices = {}
    for row in rows[1:]:
        if len(row) < 3:
            continue
        item_id = row[0]
        sell_price = row[2].replace(",", "")
        try:
            prices[item_id] = float(sell_price)
        except ValueError:
            continue
    return prices


def collect(rotation, pest_sheet, prices):
    """Gather everything we know about each crop in this rotation."""
    results = []

    for crop_name in rotation["crops"]:
        pest, item_id, drop_name, hourly_cell, threshold_cell, base_rate = CROPS[crop_name]

        if item_id is None:
            # Mushroom. Slug is the benchmark, so there is no drop to price
            # and nothing to compare against.
            price = None
            margin = None
        else:
            # .get() rather than [] because the price tab can be missing an
            # item while the sheet refreshes. Better to drop one line from the
            # message than to fail the whole command.
            price = prices.get(item_id)
            if price is None:
                margin = None
            else:
                threshold = read_cell(pest_sheet, threshold_cell)
                margin = price - threshold

        results.append({
            "crop": crop_name,
            "pest": pest,
            "drop": drop_name,
            "price": price,
            "margin": margin,
            "hourly": read_cell(pest_sheet, hourly_cell),
            "base_rate": base_rate,
        })

    return results


# ---------------------------------------------------------------- sorting

def base_rate_of(entry):
    return entry["base_rate"]


def margin_of(entry):
    """Mushroom has no margin. Counting it as zero puts it above any drop
    that is currently selling below its break-even, which is correct."""
    if entry["margin"] is None:
        return 0
    return entry["margin"]


def start_time_of(rotation):
    return int(rotation["start"])


# ---------------------------------------------------------------- the message

def render(data, rotation, pest_sheet, prices):
    entries = collect(rotation, pest_sheet, prices)

    by_crop = sorted(entries, key=base_rate_of, reverse=True)
    by_pest = sorted(entries, key=margin_of, reverse=True)

    best_crop = by_crop[0]
    second_crop = by_crop[1]
    best_pest = by_pest[0]
    second_pest = by_pest[1]

    if data["isGrandFeast"]:
        kind = "Grand"
    else:
        kind = "Harvest"

    # Worked out from the clock rather than from data["current"], so that the
    # heading still matches whichever rotation the dropdown is showing.
    now = time.time()

    if now < int(rotation["start"]):
        seen = "Upcoming"
    elif now < int(rotation["end"]):
        seen = "Current"
    else:
        seen = "Most recent"

    # "<:Wheat:123> Wheat, <:Cactus:456> Cactus, ..."
    crop_names = []
    for crop_name in rotation["crops"]:
        crop_names.append(f"{EMOJI[crop_name]} {crop_name}")
    crop_list = ", ".join(crop_names)

    lines = []
    lines.append(f"# {seen} {kind} Feast (Year {data['year']})")
    lines.append(f"<t:{rotation['start']}:f> to <t:{rotation['end']}:f>: {crop_list}")

    crop = best_crop["crop"]
    rate = best_crop["base_rate"]
    lines.append(f"**Best crop to farm**: {EMOJI[crop]} {crop} `{rate:,.0f}/h`")

    crop = second_crop["crop"]
    rate = second_crop["base_rate"]
    lines.append(f"-# Second best: {EMOJI[crop]} {crop} ({rate:,.0f}/h)")

    lines.append("")

    pest = best_pest["pest"]
    rate = best_pest["hourly"]
    lines.append(f"**Best pest to farm**: {EMOJI[pest]} {pest} `{rate:,.0f}/h`")

    if best_pest["margin"] is not None:
        drop = best_pest["drop"]
        price = best_pest["price"]
        margin = best_pest["margin"]
        lines.append(f"  * {EMOJI[drop]} {drop} `{price:,.0f}` (`{margin:+,.0f}` over threshold)")

    pest = second_pest["pest"]
    rate = second_pest["hourly"]
    runner_up = f"-# Second best: {EMOJI[pest]} {pest} ({rate:,.0f}/h)"

    if second_pest["margin"] is not None:
        drop = second_pest["drop"]
        price = second_pest["price"]
        margin = second_pest["margin"]
        runner_up += f", {EMOJI[drop]} {drop} at {price:,.0f} ({margin:+,.0f} over threshold)"

    lines.append(runner_up)

    lines.append("")
    lines.append("> Information sourced from [this spreadsheet](https://docs.google.com/spreadsheets/d/1nZI-4mNCymWb1pykwtnx--DnN_8NmEvSiDwwb9DGz8I/edit?usp=sharing)")

    return "\n".join(lines)


# ---------------------------------------------------------------- the dropdown

class Picker(discord.ui.View):
    def __init__(self, data, rotation, pest_sheet, prices):
        super().__init__(timeout=900)
        self.data = data
        self.rotation = rotation
        self.pest_sheet = pest_sheet
        self.prices = prices
        self.rotations = sorted(data["rotations"].values(), key=start_time_of)

        # One rotation means there is nothing to pick between.
        if len(self.rotations) < 2:
            return

        options = []
        for rotation_option in self.rotations[:25]:
            crops = ", ".join(rotation_option["crops"])
            options.append(discord.SelectOption(
                label=f"Month {rotation_option['month']}",
                value=rotation_option["start"],
                description=crops[:100],
                default=rotation_option["start"] == rotation["start"],
            ))

        self.select = discord.ui.Select(placeholder="Pick a rotation", options=options)
        self.select.callback = self.pick
        self.add_item(self.select)

    async def pick(self, interaction):
        chosen = self.select.values[0]

        for rotation_option in self.rotations:
            if rotation_option["start"] == chosen:
                self.rotation = rotation_option

        # Move the tick to whichever one is now on screen.
        for option in self.select.options:
            option.default = option.value == chosen

        message = render(self.data, self.rotation, self.pest_sheet, self.prices)
        await interaction.response.edit_message(content=message, view=self)


# ---------------------------------------------------------------- commands

@tree.command(name="feast", description="Best crop and pest for the Harvest Feast")
@app_commands.describe(year="Replay a past feast, e.g. 512")
async def feast(interaction: discord.Interaction, year: int = None, dump: bool = False):
    await interaction.response.defer()

    if year is not None:
        data = await get_json(f"{ROTATIONS_URL}/{year}")
    else:
        data = await get_json(ROTATIONS_URL)
        this_year = data["year"]
        # The live endpoint is only filled in while a feast is actually running.
        # When it is empty, ask for this year, then last year.
        if not data["rotations"]:
            data = await get_json(f"{ROTATIONS_URL}/{this_year}")
        if not data["rotations"]:
            data = await get_json(f"{ROTATIONS_URL}/{this_year - 1}")

    if not data["rotations"]:
        await interaction.followup.send("No feast data. Try `/feast year:512`.")
        return

    if data.get("current"):
        rotation = data["current"]
    else:
        in_order = sorted(data["rotations"].values(), key=start_time_of)
        # The first rotation that has not finished yet, which is the one
        # running now, or the next one due if the feast has not started.
        # If they have all finished, fall back to the last.
        rotation = in_order[-1]
        for candidate in in_order:
            if time.time() < int(candidate["end"]):
                rotation = candidate
                break

    pest_sheet = await get_csv(PESTS_URL)
    prices = read_prices(await get_csv(PRICES_URL))

    message = render(data, rotation, pest_sheet, prices)
    view = Picker(data, rotation, pest_sheet, prices)

    if dump:
        text = json.dumps(data, indent=4)
        file = discord.File(io.BytesIO(text.encode()), filename="rotations.json")
        await interaction.followup.send(message, file=file, view=view)

    else:
        await interaction.followup.send(message, view=view)

@tree.command(name="kernels", description="Best kernel to coin ratio for items from Feast Baker Scott's shop")
async def kernels(interaction: discord.Interaction):
    await interaction.response.defer()

    lines = []

    pest_sheet = await get_csv(PESTS_URL)

    best_item = pest_sheet[29][1]
    second_best_item = pest_sheet[30][1]
    best_kernels_needed = read_cell(pest_sheet, (29, 2))
    contact_best_kernels_needed = read_cell(pest_sheet, (29, 3))
    best_coins_per = read_cell(pest_sheet, (29, 4))
    second_best_coins_per = read_cell(pest_sheet, (30, 4))
    contact_best_coins_per = read_cell(pest_sheet, (29, 5))
    best_item_price = read_cell(pest_sheet, (29, 6))
    second_best_item_price = read_cell(pest_sheet, (30, 6))

    lines.append(f"**Best kernel to coin ratio**: {EMOJI[best_item]} {best_item} `{contact_best_coins_per:,.0f}/kernel` (sells for `{best_item_price:,.0f}`)")
    lines.append(f"* {EMOJI['Feast Baker Scott']} `{contact_best_kernels_needed:.0f}` kernels with Scott's contact, `{best_kernels_needed:.0f}` without")
    lines.append(f"  * -# Not having Scott's contact puts {best_item} at `{best_coins_per:,.0f}/kernel`")
    lines.append(f"Second best: {EMOJI[second_best_item]} {second_best_item} `{second_best_coins_per:,.0f}/kernel` (sells for `{second_best_item_price:,.0f}`)")

    lines.append("")
    lines.append("> Information sourced from [this spreadsheet](https://docs.google.com/spreadsheets/d/1nZI-4mNCymWb1pykwtnx--DnN_8NmEvSiDwwb9DGz8I/edit?usp=sharing)")

    await interaction.followup.send("\n".join(lines))

@client.event
async def on_ready():
    guild_id = os.getenv("GUILD_ID")

    if guild_id:
        target = discord.Object(id=int(guild_id))
        tree.copy_global_to(guild=target)
    else:
        target = None

    synced = await tree.sync(guild=target)
    print(f"Logged in as {client.user} - synced {len(synced)} command(s)")


if __name__ == "__main__":
    client.run(os.environ["DISCORD_TOKEN"])
