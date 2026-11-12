"""Stoichiometry Calculator built with Drafter (CS1 project).

The user builds a balanced reaction, enters masses, and the app reports the
limiting reactant, leftover reactants, theoretical yield, and percent yield.

ADVANCED TECHNIQUES USED (not covered in the course) -- each one is also
explained again, right where it is used:

1. str.maketrans / str.translate
   Builds a character-for-character translation table (here "2" -> "₂")
   and applies it to a whole string in one pass.
2. Generator expressions  (sum(x for x in ...), any(x for x in ...))
   Like a list comprehension but with no square brackets: values are
   produced one at a time instead of building a whole list in memory.
3. lambda + min(key=...)
   A lambda is a tiny unnamed function. min() calls it on every item and
   returns the item whose lambda result is smallest.
4. collections.Counter
   A dictionary subclass that counts things; missing keys count as 0, and
   two Counters can be compared with == .
5. Variadic arguments (*content)
   A parameter written with * collects any number of arguments into a
   tuple; writing *content in a call unpacks that tuple again.
6. Chained comparisons (0 <= i < len(items))
   Python lets you write two comparisons in one expression.
7. Conditional expressions (a if condition else b)
   A one-line if/else that produces a value.
8. field(default_factory=list)
   Gives each dataclass instance its OWN new list. A plain `= []` default
   would share a single list between all instances (a classic bug).
9. Routes calling other routes (return results(state))
   Calling a route function directly returns its Page, so one route can
   hand off to another without the user clicking anything.
10. Tuple unpacking in comprehensions
    [Element(s, n) for s, n in parts] splits each (symbol, count) pair.
11. Testing with bakery.assert_equal
    Compares an actual value with an expected value and reports pass/fail.
"""

from collections import Counter
from dataclasses import dataclass, field

from bakery import assert_equal
from drafter import *
from Molar_masses import MOLAR_MASSES

# =========================================
# SITE INFORMATION (required by the rubric)
# =========================================
# TODO: replace these placeholders with your real information.
set_website_title("Stoichiometry Calculator")
set_site_information(
    author="Avery Miller",
    description="Builds a chemical reaction and calculates the limitingreactant, leftovers, theoretical yield, and percent yield.",
    sources="Chat GPT and Claude",
    planning=["CS1 Final Project 0_ Pick a Problem","Avery Miller - CS1 Final Project 1_Design"],
    links=["https://github.com/averymiller08/Stoichiometry-Calculator"],
)
hide_debug_information()
set_website_framed(False)
# =========================================
# STYLE CONSTANTS
# =========================================
# Keeping colors in one place means a redesign only touches these lines.
# (Global *constants* are allowed by the rubric; global variables are not.)
PRIMARY = "#1f4e79"
ERROR_COLOR = "#b00020"
CARD_BG = "#f4f8fb"
CARD_BORDER = "1px solid #b7cde0"

# Maps the characters 0-9 to their Unicode subscript versions.
# ADVANCED: str.maketrans builds a translation table once; str.translate
# then applies it to a whole string in a single pass (faster and cleaner
# than looping over every character).
SUBSCRIPT_TABLE = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


# =========================================
# DATA CLASSES
# =========================================
@dataclass
class Element:
    """One element inside a molecule, e.g. the 'H2' in H2O.

    Attributes:
        abbreviation: Chemical symbol such as "H" or "Fe".
        subscript: How many atoms of this element are in one molecule.
    """
    abbreviation: str
    subscript: int


@dataclass
class Molecule:
    """A molecule in a reaction, with its coefficient and mass information.

    Attributes:
        coefficient: Balancing coefficient in front of the formula.
        elements: The elements (with subscripts) that make up the molecule.
        grams: Mass entered by the user (reactant given, or product collected).
        excess: True if this reactant is in excess and has no known mass.
    """
    coefficient: int
    elements: list[Element]
    grams: float
    excess: bool = False


@dataclass
class State:
    """Everything the app remembers between pages.

    Drafter passes this object to every route. Because it is a dataclass,
    Drafter can save and restore it automatically.

    ADVANCED: list fields use field(default_factory=list) so that every
    State() gets its own fresh list instead of sharing one list.
    """
    reactants: list[Molecule] = field(default_factory=list)
    products: list[Molecule] = field(default_factory=list)

    # Molecule currently being built
    draft_kind: str = ""
    draft_coefficient: int = 1
    draft_elements: list[Element] = field(default_factory=list)

    # Mass input progress
    mass_group: str = "reactants"
    mass_index: int = 0
    error: str = ""

    # Finished results, stored as table rows (lists of strings)
    summary: str = ""                       # Error message if calculation fails
    result_reaction: str = ""
    result_limiting: str = ""
    result_leftovers: list[list[str]] = field(default_factory=list)
    result_yields: list[list[str]] = field(default_factory=list)


# =========================================
# CHEMISTRY FUNCTIONS
# =========================================
def molecular_weight(molecule: Molecule) -> float:
    """Return the molar mass of a molecule in g/mol.

    ADVANCED: a generator expression inside sum(). Each element's molar mass
    is multiplied by its subscript and sum() adds the values as they are
    produced, without first building a list.

    Args:
        molecule: The molecule whose molar mass is wanted.

    Returns:
        Molar mass in grams per mole.
    """
    return sum(
        MOLAR_MASSES[element.abbreviation] * element.subscript
        for element in molecule.elements
    )


def calculate_moles(molecule: Molecule) -> float:
    """Convert the molecule's grams to moles (grams / molar mass).

    Args:
        molecule: A molecule with its grams attribute filled in.

    Returns:
        The amount of the molecule in moles.
    """
    return molecule.grams / molecular_weight(molecule)


def molecule_formula(molecule: Molecule) -> str:
    """Return the formula with Unicode subscripts, e.g. 'H₂O'.

    A subscript of 1 is hidden, as in normal chemical notation.

    Args:
        molecule: The molecule to format.

    Returns:
        The formula text without the coefficient.
    """
    formula = ""
    for element in molecule.elements:
        formula += element.abbreviation
        if element.subscript != 1:
            # str(2) -> "2", then .translate converts it to "₂"
            formula += str(element.subscript).translate(SUBSCRIPT_TABLE)
    return formula


def molecule_name(molecule: Molecule) -> str:
    """Return the coefficient followed by the formula, e.g. '2H₂O'.

    A coefficient of 1 is hidden, as in normal chemical notation.

    Args:
        molecule: The molecule to format.

    Returns:
        Coefficient (if not 1) followed by the formula.
    """
    prefix = "" if molecule.coefficient == 1 else str(molecule.coefficient)
    return prefix + molecule_formula(molecule)


def reaction_text(state: State) -> str:
    """Return the full equation as text, e.g. '2H₂ + O₂  →  2H₂O'.

    Uses list comprehensions to convert each molecule to text, then
    str.join to place ' + ' between them (no trailing separator to trim).

    Args:
        state: The app state holding the reactants and products.

    Returns:
        The equation as a single string.
    """
    reactants = " + ".join([molecule_name(m) for m in state.reactants])
    products = " + ".join([molecule_name(m) for m in state.products])
    return reactants + "  →  " + products


def find_limiting_reactant(reactants: list[Molecule]) -> Molecule:
    """Return the reactant that runs out first.

    A reactant's "ratio" is moles / coefficient. The smallest ratio is the
    limiting reactant. Reactants marked excess are ignored.

    ADVANCED: min() accepts a key function that says what to compare by.
    The lambda is a tiny unnamed function that computes each ratio.

    Args:
        reactants: All reactants in the reaction.

    Returns:
        The limiting reactant.

    Raises:
        ValueError: If every reactant is marked excess.
    """
    available = [r for r in reactants if not r.excess]
    if len(available) == 0:
        raise ValueError("At least one reactant needs a known mass.")

    return min(available, key=lambda r: calculate_moles(r) / r.coefficient)


def expected_yield(reactants: list[Molecule], product: Molecule) -> float:
    """Return the theoretical yield of a product in grams.

    Converts limiting-reactant moles to product moles using the coefficient
    ratio, then converts product moles to grams.

    Args:
        reactants: All reactants in the reaction.
        product: The product whose yield is wanted.

    Returns:
        Theoretical yield in grams.
    """
    limiting = find_limiting_reactant(reactants)
    product_moles = (
        calculate_moles(limiting) / limiting.coefficient * product.coefficient
    )
    return product_moles * molecular_weight(product)


def percent_yield(reactants: list[Molecule], product: Molecule) -> float:
    """Return actual yield / theoretical yield * 100 (0 if theoretical is 0).

    Args:
        reactants: All reactants in the reaction.
        product: The product, whose grams attribute is the actual yield.

    Returns:
        The percent yield.
    """
    theoretical = expected_yield(reactants, product)
    if theoretical <= 0:
        return 0
    return product.grams / theoretical * 100


def leftover_reactant(reactants: list[Molecule], reactant: Molecule) -> float:
    """Return grams of a reactant left over, or -1 if it is marked excess.

    Tiny negative or near-zero values caused by floating-point rounding are
    treated as exactly 0.

    Args:
        reactants: All reactants in the reaction.
        reactant: The reactant whose leftover amount is wanted.

    Returns:
        Leftover grams, or -1 when the reactant is in excess (unknown mass).
    """
    if reactant.excess:
        return -1

    limiting = find_limiting_reactant(reactants)
    moles_used = (
        calculate_moles(limiting) / limiting.coefficient * reactant.coefficient
    )
    remaining_moles = calculate_moles(reactant) - moles_used
    if remaining_moles < 0.0000001:
        remaining_moles = 0
    return remaining_moles * molecular_weight(reactant)


def count_atoms(molecules: list[Molecule]) -> Counter:
    """Count the total atoms of each element across a list of molecules.

    ADVANCED: Counter is a dictionary subclass that treats missing keys as
    0, so we can use += without first checking whether the key exists.

    Args:
        molecules: The molecules on one side of the equation.

    Returns:
        A Counter mapping element symbol to total atom count.
    """
    totals = Counter()
    for molecule in molecules:
        for element in molecule.elements:
            totals[element.abbreviation] += element.subscript * molecule.coefficient
    return totals


def reaction_is_balanced(state: State) -> bool:
    """Return True if both sides have the same atoms of every element.

    Two Counters compare equal when they hold identical keys and counts.

    Args:
        state: The app state holding the reactants and products.

    Returns:
        True when the equation is balanced.
    """
    return count_atoms(state.reactants) == count_atoms(state.products)


def reset_mass_inputs(state: State) -> None:
    """Clear all entered masses and restart mass entry from the first reactant.

    Called whenever the reaction changes, since old masses may no longer apply.

    Args:
        state: The app state; it is modified in place.
    """
    for molecule in state.reactants + state.products:
        molecule.grams = 0.0
        molecule.excess = False
    state.mass_group = "reactants"
    state.mass_index = 0


# =========================================
# UI HELPERS
# =========================================
def card(*content) -> Div:
    """Wrap components in a shaded, bordered box.

    ADVANCED: the * in the parameter list collects any number of arguments
    into a tuple (variadic arguments). Div(*content) then unpacks that tuple
    back into separate arguments.

    Not unit tested: it returns a Drafter component, and comparing styled
    components is not reliable, so it is checked visually instead.

    Args:
        *content: Any number of Drafter components or strings.

    Returns:
        A styled Div containing the content.
    """
    box = Div(*content)
    box = change_background_color(box, CARD_BG)
    box = change_border(box, CARD_BORDER)
    box = change_padding(box, "12px")
    return box


def error_box(message: str):
    """Return a red, bold error message (or an empty string if none).

    Args:
        message: The error text; an empty string means "no error".

    Returns:
        A styled component, or "" when there is no message.
    """
    if message == "":
        return ""
    return change_color(bold("⚠ " + message), ERROR_COLOR)


def progress(step: int) -> str:
    """Return a 'Step X of 4' label shown at the top of the main pages.

    Args:
        step: The current step number (1 to 4).

    Returns:
        The label text.
    """
    return "Step " + str(step) + " of 4"


def title(text: str):
    """Return a page title (a Header) in the app's primary color.

    Not unit tested: it returns a styled Drafter component (see card()).

    Args:
        text: The title text.

    Returns:
        A colored Header component.
    """
    return change_color(Header(text), PRIMARY)


# =========================================
# ROUTE 1: HOME PAGE
# =========================================
@route
def index(state: State, restart: bool = False) -> Page:
    """Home page. If restart is True, wipe all saved data first.

    Args:
        state: The current app state.
        restart: True to replace the state with a brand-new State.

    Returns:
        The home page.
    """
    if restart:
        state = State()

    return Page(state, [
        title("Stoichiometry Calculator"),
        "Build a chemical reaction and calculate its limiting reactant, "
        "theoretical yield, leftover reactants, and percent yield.",
        HorizontalRule(),
        Header("What can this app calculate?", 2),
        NumberedList([
            "Limiting reactant",
            "Theoretical yield",
            "Leftover reactants",
            "Percent yield",
        ]),
        HorizontalRule(),
        Button("Start building your reaction", "reaction_builder"),
    ])


# =========================================
# ROUTE 2: REACTION BUILDER
# =========================================
@route
def reaction_builder(state: State) -> Page:
    """Menu page where the user chooses to add a reactant or a product.

    Args:
        state: The current app state (not modified).

    Returns:
        The reaction builder menu page.
    """
    return Page(state, [
        title("Build Your Reaction"),
        progress(1),
        card(
            Header("Reactants", 3),
            "Substances that begin a chemical reaction.",
            LineBreak(),
            Button("Add reactant", "molecule_builder",
                   [Argument("kind", "reactant")]),
        ),
        LineBreak(),
        card(
            Header("Products", 3),
            "Substances created by the chemical reaction.",
            LineBreak(),
            Button("Add product", "molecule_builder",
                   [Argument("kind", "product")]),
        ),
        HorizontalRule(),
        Button("Review my reaction", "reaction_review"),
        Button("Back to home", "index"),
    ])


# =========================================
# ROUTE 3: MOLECULE BUILDER
# =========================================
@route
def molecule_builder(
    state: State,
    kind: str = "",
    action: str = "",
    coefficient: str = "",
    symbol: str = "",
    subscript: str = "",
) -> Page:
    """Build one molecule element-by-element.

    One route handles several jobs, chosen by the `action` argument:
      - kind != ""          -> start a brand-new draft molecule
      - action == "add"     -> append the typed element to the draft
      - action == "delete_element" -> remove the last element
      - action == "save"    -> finish the molecule and go to review

    Arguments come from TextBoxes (always strings), so they are converted
    and validated inside try/except. Raising ValueError on bad input jumps
    straight to the shared error message.

    Args:
        state: The current app state; the draft fields are modified.
        kind: "reactant" or "product" when starting a new molecule.
        action: Which job to perform ("add", "delete_element", "save").
        coefficient: Text from the coefficient TextBox.
        symbol: Text from the element-symbol TextBox.
        subscript: Text from the subscript TextBox.

    Returns:
        The molecule builder page, or the reaction review page after a
        successful save.
    """
    # Start a new molecule
    if kind != "":
        state.draft_kind = kind
        state.draft_coefficient = 1
        state.draft_elements = []
        state.error = ""

    # Add an element
    if action == "add":
        try:
            new_coefficient = int(coefficient)
            new_subscript = int(subscript)
            symbol = symbol.strip().capitalize()   # "fE " -> "Fe"

            if new_coefficient <= 0 or new_subscript <= 0:
                raise ValueError
            if symbol not in MOLAR_MASSES:
                raise ValueError

            state.draft_coefficient = new_coefficient
            state.draft_elements.append(Element(symbol, new_subscript))
            state.error = ""
        except ValueError:
            state.error = (
                "Please enter a valid coefficient, element symbol, "
                "and subscript."
            )

    # Delete the last element
    if action == "delete_element":
        if len(state.draft_elements) > 0:
            state.draft_elements.pop()

    # Save the molecule
    if action == "save":
        try:
            new_coefficient = int(coefficient)
            if new_coefficient <= 0:
                raise ValueError
            state.draft_coefficient = new_coefficient

            # Allow saving with one last element still typed in the boxes
            if symbol.strip() != "":
                symbol = symbol.strip().capitalize()
                new_subscript = int(subscript)
                if symbol not in MOLAR_MASSES or new_subscript <= 0:
                    raise ValueError
                state.draft_elements.append(Element(symbol, new_subscript))

            if len(state.draft_elements) == 0:
                raise ValueError

            new_molecule = Molecule(
                state.draft_coefficient,
                state.draft_elements.copy(),   # copy so clearing the draft is safe
                0.0,
            )
            if state.draft_kind == "reactant":
                state.reactants.append(new_molecule)
            else:
                state.products.append(new_molecule)

            state.draft_elements = []
            state.error = ""
            reset_mass_inputs(state)
            # ADVANCED: calling another route directly returns its Page,
            # so we "redirect" to the review page without a button click.
            return reaction_review(state)
        except ValueError:
            state.error = (
                "Check your coefficient, elements, and subscripts. "
                "You must add at least one element."
            )

    # ----- Build the page -----
    if len(state.draft_elements) > 0:
        preview_text = molecule_name(
            Molecule(state.draft_coefficient, state.draft_elements, 0.0)
        )
    else:
        preview_text = "Your molecule will appear here."

    # A list comprehension turns every Element into one line of text.
    # Because it is built from the loop's own list, the lines always match
    # the draft exactly.
    element_lines = [
        element.abbreviation + "  (subscript " + str(element.subscript) + ")"
        for element in state.draft_elements
    ]

    content = [
        title("Molecule Builder"),
        "Currently adding a " + state.draft_kind + ".",
        card(
            Header("Preview", 3),
            change_width(bold(preview_text), "24px"),
        ),
        HorizontalRule(),
        Header("Step 1: Coefficient", 3),
        TextBox("coefficient", str(state.draft_coefficient), "number"),
        Header("Step 2: Elements", 3),
    ]

    if element_lines:
        content.append(NumberedList(element_lines))
    else:
        content.append(italic("No elements added yet."))

    content.extend([
        "Element symbol (for example, Fe):",
        TextBox("symbol", "", "text"),
        "Subscript:",
        TextBox("subscript", "1", "number"),
        error_box(state.error),
        Button("Add element", "molecule_builder", [Argument("action", "add")]),
        Button("Delete last element", "molecule_builder",
               [Argument("action", "delete_element")]),
        HorizontalRule(),
        Button("Save molecule", "molecule_builder",
               [Argument("action", "save")]),
        Button("Cancel", "reaction_review"),
    ])
    return Page(state, content)


# =========================================
# ROUTE 4: REACTION REVIEW
# =========================================
@route
def reaction_review(
    state: State,
    delete_reactant: int = -1,
    delete_product: int = -1,
) -> Page:
    """Show the current equation and let the user delete molecules.

    A delete index of -1 means "nothing to delete". ADVANCED: the chained
    comparison 0 <= i < len(list) checks that the index is valid in one
    expression (it means 0 <= i AND i < len(list)).

    Args:
        state: The current app state; molecules may be removed from it.
        delete_reactant: Index of the reactant to delete, or -1 for none.
        delete_product: Index of the product to delete, or -1 for none.

    Returns:
        The reaction review page.
    """
    if 0 <= delete_reactant < len(state.reactants):
        state.reactants.pop(delete_reactant)
        reset_mass_inputs(state)

    if 0 <= delete_product < len(state.products):
        state.products.pop(delete_product)
        reset_mass_inputs(state)

    content = [
        title("Reaction Review"),
        progress(2),
        card(
            Header("Your reaction", 3),
            change_width(bold(reaction_text(state)), "22px"),
        ),
        HorizontalRule(),
        Header("Reactants", 3),
    ]

    if len(state.reactants) == 0:
        content.append(italic("You have not added any reactants."))
    for i, molecule in enumerate(state.reactants):
        content.append(bold(molecule_name(molecule)))
        content.append(Button("Delete", "reaction_review",
                              [Argument("delete_reactant", i)]))

    content.append(Header("Products", 3))
    if len(state.products) == 0:
        content.append(italic("You have not added any products."))
    for i, molecule in enumerate(state.products):
        content.append(bold(molecule_name(molecule)))
        content.append(Button("Delete", "reaction_review",
                              [Argument("delete_product", i)]))

    content.extend([
        HorizontalRule(),
        Button("Add another reactant", "molecule_builder",
               [Argument("kind", "reactant")]),
        Button("Add another product", "molecule_builder",
               [Argument("kind", "product")]),
    ])

    if len(state.reactants) > 0 and len(state.products) > 0:
        content.append(Button("Continue to mass input", "mass_input"))
    content.append(Button("Back to reaction builder", "reaction_builder"))
    return Page(state, content)


# =========================================
# ROUTE 5: MASS INPUT
# =========================================
@route
def mass_input(state: State, grams: str = "") -> Page:
    """Collect one mass at a time: every reactant first, then every product.

    state.mass_group ("reactants" or "products") and state.mass_index track
    where we are. Each submission saves the mass, advances the index, and
    re-renders this same route for the next molecule. When all masses are
    entered, it hands off to results().

    Args:
        state: The current app state; masses and progress are modified.
        grams: Text from the grams TextBox (a number, or "Excess" for a
            reactant). An empty string means nothing was submitted yet.

    Returns:
        The mass input page for the next molecule, or the results page
        once every mass has been entered.
    """
    # Save the submitted mass
    if grams.strip() != "":
        try:
            typed_excess = grams.strip().lower() == "excess"

            if state.mass_group == "reactants":
                molecule = state.reactants[state.mass_index]
                if typed_excess:
                    molecule.excess = True
                    molecule.grams = 0.0
                else:
                    mass = float(grams)
                    if mass <= 0:
                        raise ValueError
                    molecule.grams = mass
                    molecule.excess = False
            else:
                if typed_excess:        # products can't be "excess"
                    raise ValueError
                mass = float(grams)
                if mass <= 0:
                    raise ValueError
                molecule = state.products[state.mass_index]
                molecule.grams = mass
                molecule.excess = False

            state.mass_index += 1
            state.error = ""
        except ValueError:
            state.error = 'Enter a positive mass or type "Excess" for a reactant.'

    # Move from reactants to products
    if state.mass_group == "reactants" and state.mass_index >= len(state.reactants):
        state.mass_group = "products"
        state.mass_index = 0

    # Finish mass entry
    if state.mass_group == "products" and state.mass_index >= len(state.products):
        return results(state)

    # Identify the current molecule.
    # ADVANCED: a conditional expression (a if condition else b) picks the
    # right list in one line.
    is_reactant = state.mass_group == "reactants"
    group = state.reactants if is_reactant else state.products
    molecule = group[state.mass_index]

    if is_reactant:
        heading = "Reactant mass"
        instructions = (
            'Enter the mass in grams, or type "Excess" if it is in excess.'
        )
    else:
        heading = "Actual product mass"
        instructions = (
            "Enter the amount of product you actually collected, in grams."
        )

    return Page(state, [
        title("Mass Input"),
        progress(3),
        italic(heading + " — molecule " + str(state.mass_index + 1)
               + " of " + str(len(group))),
        card(
            change_width(bold(molecule_name(molecule)), "26px"),
            instructions,
            "Grams:",
            TextBox("grams", "", "text"),
        ),
        error_box(state.error),
        Button("Save and continue", "mass_input"),
        Button("Back to reaction review", "reaction_review"),
    ])


# =========================================
# ROUTE 6: RESULTS
# =========================================
@route
def results(state: State) -> Page:
    """Validate the reaction, run every calculation, and store the results.

    On any validation problem the message goes into state.summary and the
    user is sent to summary(). On success the structured results (table
    rows) are stored in state for summary() to display.

    ADVANCED: any(...) with a generator expression stops at the first True
    and never builds a list.

    Args:
        state: The current app state; the result fields are modified.

    Returns:
        The "calculations complete" page, or the summary page showing an
        error message if validation failed.
    """
    # ----- Validation -----
    if len(state.reactants) == 0 or len(state.products) == 0:
        state.summary = "You need at least one reactant and one product."
        return summary(state)

    if any(m.grams <= 0 and not m.excess for m in state.reactants):
        state.summary = "A reactant is missing its mass."
        return summary(state)

    if any(m.grams <= 0 for m in state.products):
        state.summary = "A product is missing its actual mass."
        return summary(state)

    if not reaction_is_balanced(state):
        state.summary = (
            "Your reaction is not balanced. "
            "Please return and correct the equation."
        )
        return summary(state)

    try:
        limiting = find_limiting_reactant(state.reactants)
    except ValueError:
        state.summary = "At least one reactant must have a known mass."
        return summary(state)

    # ----- Build structured results -----
    state.summary = ""
    state.result_reaction = reaction_text(state)
    state.result_limiting = molecule_name(limiting)

    # First row of each table is the header row.
    state.result_leftovers = [["Reactant", "Leftover"]]
    for reactant in state.reactants:
        if reactant.excess:
            amount = "Excess (amount unknown)"
        else:
            amount = str(round(leftover_reactant(state.reactants, reactant), 3)) + " g"
        state.result_leftovers.append([molecule_name(reactant), amount])

    state.result_yields = [["Product", "Theoretical", "Actual", "Percent yield"]]
    for product in state.products:
        theoretical = expected_yield(state.reactants, product)
        percent = percent_yield(state.reactants, product)
        state.result_yields.append([
            molecule_name(product),
            str(round(theoretical, 3)) + " g",
            str(round(product.grams, 3)) + " g",
            str(round(percent, 2)) + "%",
        ])

    return Page(state, [
        title("Calculations Complete"),
        progress(4),
        "Your reaction has been calculated successfully.",
        Button("View my results", "summary"),
    ])


# =========================================
# ROUTE 7: SUMMARY
# =========================================
@route
def summary(state: State) -> Page:
    """Display either an error message or the full results tables.

    Args:
        state: The current app state (not modified).

    Returns:
        The error page if state.summary is not empty, otherwise the page
        with the results tables.
    """
    if state.summary != "":
        return Page(state, [
            title("Something Needs Fixing"),
            error_box(state.summary),
            HorizontalRule(),
            Button("Return to reaction review", "reaction_review"),
            Button("Start a new reaction", "index", [Argument("restart", True)]),
        ])

    return Page(state, [
        title("Your Stoichiometry Results"),
        card(
            Header("Reaction", 3),
            change_width(bold(state.result_reaction), "22px"),
        ),
        LineBreak(),
        card(
            Header("Limiting reactant", 3),
            change_width(bold(state.result_limiting), "22px"),
        ),
        Header("Leftover reactants", 3),
        Table(state.result_leftovers),
        Header("Product yields", 3),
        Table(state.result_yields),
        HorizontalRule(),
        Button("Start a new reaction", "index", [Argument("restart", True)]),
        Button("Return to reaction review", "reaction_review"),
    ])


# =========================================
# UNIT TESTS
# =========================================
# Testing notes:
# * Every test builds FRESH data with make_state(), because many functions
#   (and every route) modify the objects they are given. Sharing one state
#   between tests would let one test break another.
# * Expected molar masses are computed from MOLAR_MASSES instead of being
#   typed in, so the tests stay correct if the table's precision changes.
# * Route tests check the Page's state (page.state) and its effects. They do
#   not compare whole pages, because styled components are not reliable to
#   compare with ==.
# * The tests are inside functions so no global variables are created.

def make_molecule(
    coefficient: int,
    parts: list[tuple[str, int]],
    grams: float = 0.0,
) -> Molecule:
    """Build a Molecule from (symbol, subscript) pairs for use in tests.

    ADVANCED: the list comprehension unpacks each tuple into s and n
    ("tuple unpacking"), so [("H", 2), ("O", 1)] becomes two Elements.

    Args:
        coefficient: The balancing coefficient.
        parts: Pairs of (element symbol, subscript).
        grams: The mass to store on the molecule.

    Returns:
        A new Molecule.
    """
    return Molecule(coefficient, [Element(s, n) for s, n in parts], grams)


def make_state() -> State:
    """Return a fresh State holding the balanced reaction 2H2 + O2 -> 2H2O.

    Returns:
        A new State with two reactants and one product, all masses 0.
    """
    return State(
        reactants=[make_molecule(2, [("H", 2)]), make_molecule(1, [("O", 2)])],
        products=[make_molecule(2, [("H", 2), ("O", 1)])],
    )


def make_state_with_masses() -> State:
    """Return make_state() with 1 g of H2, 100 g of O2, and 5 g of water.

    H2 is clearly the limiting reactant (1 g of H2 is about 0.5 mol, while
    100 g of O2 is over 3 mol).

    Returns:
        A new State ready for the calculation functions.
    """
    state = make_state()
    state.reactants[0].grams = 1.0
    state.reactants[1].grams = 100.0
    state.products[0].grams = 5.0
    return state


def test_formatting_functions() -> None:
    """Test the text-formatting helpers."""
    state = make_state()
    water = state.products[0]
    # Subscript of 1 is hidden; subscript 2 becomes a Unicode subscript.
    assert_equal(molecule_formula(water), "H₂O")
    assert_equal(molecule_formula(state.reactants[1]), "O₂")
    # Coefficient of 1 is hidden.
    assert_equal(molecule_name(water), "2H₂O")
    assert_equal(molecule_name(state.reactants[1]), "O₂")
    assert_equal(reaction_text(state), "2H₂ + O₂  →  2H₂O")
    assert_equal(progress(3), "Step 3 of 4")
    assert_equal(error_box(""), "")
    # Multi-digit subscripts use every digit.
    assert_equal(molecule_formula(make_molecule(1, [("C", 12)])), "C₁₂")


def test_chemistry_functions() -> None:
    """Test molar mass, moles, limiting reactant, yields, and leftovers."""
    state = make_state_with_masses()
    h2, o2 = state.reactants
    water = state.products[0]
    h, o = MOLAR_MASSES["H"], MOLAR_MASSES["O"]

    # Molar mass and moles
    assert_equal(round(molecular_weight(water), 6), round(2 * h + o, 6))
    assert_equal(round(calculate_moles(h2), 6), round(1.0 / (2 * h), 6))

    # Limiting reactant
    assert_equal(molecule_name(find_limiting_reactant(state.reactants)), "2H₂")
    o2_only = make_state_with_masses()
    o2_only.reactants[0].excess = True        # ignore H2
    assert_equal(
        molecule_name(find_limiting_reactant(o2_only.reactants)), "O₂"
    )
    all_excess = make_state()
    for reactant in all_excess.reactants:
        reactant.excess = True
    raised = False
    try:
        find_limiting_reactant(all_excess.reactants)
    except ValueError:
        raised = True
    assert_equal(raised, True)

    # Theoretical yield: 2 H2 -> 2 H2O, so moles of water = moles of H2.
    theoretical = expected_yield(state.reactants, water)
    assert_equal(round(theoretical, 6), round((2 * h + o) / (2 * h), 6))

    # Percent yield: collecting half of the theoretical amount gives 50%.
    water.grams = theoretical / 2
    assert_equal(round(percent_yield(state.reactants, water), 6), 50.0)

    # Leftovers: limiting reactant is used up, excess marker returns -1.
    assert_equal(leftover_reactant(state.reactants, h2), 0.0)
    assert_equal(
        round(leftover_reactant(state.reactants, o2), 6),
        round(100.0 - o / (2 * h), 6),
    )
    o2.excess = True
    assert_equal(leftover_reactant(state.reactants, o2), -1)


def test_balancing_functions() -> None:
    """Test atom counting and balance checking."""
    state = make_state()
    assert_equal(count_atoms(state.reactants), Counter({"H": 4, "O": 2}))
    assert_equal(count_atoms(state.products), Counter({"H": 4, "O": 2}))
    assert_equal(reaction_is_balanced(state), True)
    state.products[0].coefficient = 1          # now 2 H on the right only
    assert_equal(reaction_is_balanced(state), False)


def test_reset_mass_inputs() -> None:
    """Test that reset_mass_inputs clears masses and progress."""
    state = make_state_with_masses()
    state.reactants[1].excess = True
    state.mass_group = "products"
    state.mass_index = 1
    reset_mass_inputs(state)
    assert_equal(state.reactants[0].grams, 0.0)
    assert_equal(state.reactants[1].excess, False)
    assert_equal(state.products[0].grams, 0.0)
    assert_equal(state.mass_group, "reactants")
    assert_equal(state.mass_index, 0)


def test_index_route() -> None:
    """Test the home route, with and without restart."""
    assert_equal(index(make_state()).state, make_state())
    assert_equal(index(make_state(), True).state, State())


def test_reaction_builder_route() -> None:
    """Test that the menu route shows the page without changing state."""
    assert_equal(reaction_builder(make_state()).state, make_state())


def test_molecule_builder_route() -> None:
    """Test starting, adding, deleting, and saving in the molecule builder."""
    # Start a new draft
    state = State()
    page = molecule_builder(state, kind="reactant")
    assert_equal(page.state.draft_kind, "reactant")
    assert_equal(page.state.draft_elements, [])

    # Add a valid element (symbol is cleaned up: " h " -> "H")
    page = molecule_builder(
        state, action="add", coefficient="2", symbol=" h ", subscript="2"
    )
    assert_equal(page.state.draft_elements, [Element("H", 2)])
    assert_equal(page.state.draft_coefficient, 2)
    assert_equal(page.state.error, "")

    # Invalid symbol is rejected and sets an error
    page = molecule_builder(
        state, action="add", coefficient="2", symbol="Xx", subscript="1"
    )
    assert_equal(len(page.state.draft_elements), 1)
    assert_equal(page.state.error != "", True)

    # Delete the last element
    page = molecule_builder(state, action="delete_element")
    assert_equal(page.state.draft_elements, [])

    # Saving with no elements fails
    page = molecule_builder(state, action="save", coefficient="1")
    assert_equal(len(page.state.reactants), 0)
    assert_equal(page.state.error != "", True)

    # Saving with one last element typed in the boxes succeeds
    page = molecule_builder(
        state, action="save", coefficient="2", symbol="h", subscript="2"
    )
    assert_equal(len(page.state.reactants), 1)
    assert_equal(molecule_name(page.state.reactants[0]), "2H₂")
    assert_equal(page.state.draft_elements, [])

    # Products go into the products list
    state.draft_kind = "product"
    page = molecule_builder(
        state, action="save", coefficient="1", symbol="o", subscript="2"
    )
    assert_equal(len(page.state.products), 1)


def test_reaction_review_route() -> None:
    """Test deleting molecules and ignoring invalid indexes."""
    state = make_state()
    assert_equal(len(reaction_review(state, delete_reactant=5).state.reactants), 2)
    assert_equal(len(reaction_review(state, delete_reactant=-1).state.reactants), 2)

    state.products[0].grams = 5.0
    page = reaction_review(state, delete_reactant=0)
    assert_equal(len(page.state.reactants), 1)
    assert_equal(page.state.products[0].grams, 0.0)   # masses were reset

    page = reaction_review(state, delete_product=0)
    assert_equal(len(page.state.products), 0)


def test_mass_input_route() -> None:
    """Test saving masses, the excess keyword, errors, and finishing."""
    # Reactant mass is saved and the index advances
    state = make_state()
    page = mass_input(state, "1.5")
    assert_equal(page.state.reactants[0].grams, 1.5)
    assert_equal(page.state.mass_index, 1)

    # "Excess" is accepted for a reactant; mass entry then moves to products
    page = mass_input(state, "Excess")
    assert_equal(page.state.reactants[1].excess, True)
    assert_equal(page.state.mass_group, "products")
    assert_equal(page.state.mass_index, 0)

    # A bad mass sets an error and does not advance
    bad = make_state()
    page = mass_input(bad, "-3")
    assert_equal(page.state.error != "", True)
    assert_equal(page.state.mass_index, 0)

    # Products cannot be "excess"
    bad.mass_group = "products"
    page = mass_input(bad, "excess")
    assert_equal(page.state.error != "", True)
    assert_equal(page.state.products[0].grams, 0.0)

    # Entering the last product mass hands off to results()
    done = make_state()
    done.reactants[0].grams = 1.0
    done.reactants[1].grams = 100.0
    done.mass_group = "products"
    page = mass_input(done, "3.0")
    assert_equal(page.state.result_limiting, "2H₂")


def test_results_route() -> None:
    """Test every validation message and a successful calculation."""
    # No molecules at all
    page = results(State())
    assert_equal(page.state.summary,
                 "You need at least one reactant and one product.")

    # Missing reactant mass
    page = results(make_state())
    assert_equal(page.state.summary, "A reactant is missing its mass.")

    # Missing product mass
    state = make_state_with_masses()
    state.products[0].grams = 0.0
    assert_equal(results(state).state.summary,
                 "A product is missing its actual mass.")

    # Unbalanced equation
    state = make_state_with_masses()
    state.products[0].coefficient = 1
    assert_equal(
        results(state).state.summary,
        "Your reaction is not balanced. Please return and correct the equation.",
    )

    # Every reactant marked excess
    state = make_state_with_masses()
    for reactant in state.reactants:
        reactant.excess = True
        reactant.grams = 0.0
    assert_equal(results(state).state.summary,
                 "At least one reactant must have a known mass.")

    # Success
    state = make_state_with_masses()
    page = results(state)
    assert_equal(page.state.summary, "")
    assert_equal(page.state.result_reaction, "2H₂ + O₂  →  2H₂O")
    assert_equal(page.state.result_limiting, "2H₂")
    assert_equal(page.state.result_leftovers[0], ["Reactant", "Leftover"])
    assert_equal(len(page.state.result_leftovers), 3)
    assert_equal(page.state.result_leftovers[1][1], "0.0 g")
    assert_equal(page.state.result_yields[0],
                 ["Product", "Theoretical", "Actual", "Percent yield"])
    assert_equal(len(page.state.result_yields), 2)


def test_summary_route() -> None:
    """Test that summary keeps the error message / results in state."""
    state = make_state()
    state.summary = "Something went wrong."
    assert_equal(summary(state).state.summary, "Something went wrong.")

    good = make_state_with_masses()
    results(good)
    page = summary(good)
    assert_equal(page.state.summary, "")
    assert_equal(page.state.result_limiting, "2H₂")


def run_tests() -> None:
    """Run every unit test; assert_equal prints a pass/fail line for each."""
    test_formatting_functions()
    test_chemistry_functions()
    test_balancing_functions()
    test_reset_mass_inputs()
    test_index_route()
    test_reaction_builder_route()
    test_molecule_builder_route()
    test_reaction_review_route()
    test_mass_input_route()
    test_results_route()
    test_summary_route()


# =========================================
# START APPLICATION
# =========================================
run_tests()
start_server(State())
