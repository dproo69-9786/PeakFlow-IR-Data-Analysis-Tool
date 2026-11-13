from drafter import *
from dataclasses import dataclass


set_site_information(
    author="Your Name",
    description="Compare FTIR peak areas across samples.",
    sources=[],
    planning="",
    links=[]
)

hide_debug_information()


# ------------------------------------------------------------
# Dataclasses

@dataclass
class Spectrum:
    """Store the data from one uploaded FTIR sample."""

    name: str
    wavenumbers: list[float]
    intensities: list[float]


@dataclass
class State:
    """Store information shared between website pages."""

    spectra: dict[str, Spectrum]
    reference_range: list[float]
    target_ranges: list[list[float]]
    signal_type: str
    baseline_sample: str
    results: dict


# ------------------------------------------------------------
# Helper functions

def parseSpectrumText(text: str) -> list[list[float], list[float]]:
    """Extract wavenumbers and intensities from a TXT file."""

    wavenumbers = []
    intensities = []

    for line in text.splitlines():
        parts = line.replace(",", " ").split()

        if len(parts) >= 2:
            try:
                wavenumber = float(parts[0])
                intensity = float(parts[1])

                wavenumbers.append(wavenumber)
                intensities.append(intensity)

            except ValueError:
                continue

    return wavenumbers, intensities


def parseRange(start_text: str, end_text: str) -> list[float]:
    """Convert two inputs into a valid wavenumber range."""

    try:
        start = float(start_text)
        end = float(end_text)

    except ValueError:
        return None

    if start >= end:
        return None

    return [start, end]


def calculateAUC(wavenumbers: list[float], intensities: list[float], peak_range: list[float]) -> float:
    """Calculate the trapezoidal area within a selected range."""

    points = []

    # Collect data points inside the selected range.
    for i in range(len(wavenumbers)):
        wavenumber = wavenumbers[i]
        intensity = intensities[i]

        if (peak_range[0] <= wavenumber
                and wavenumber <= peak_range[1]):
            points.append([wavenumber, intensity])

    # At least two points are needed to calculate an area.
    if len(points) < 2:
        return None

    # Arrange points from lowest to highest wavenumber.
    # This uses a basic sorting method with two loops.
    for i in range(len(points)):
        for j in range(len(points) - i - 1):
            if points[j][0] > points[j + 1][0]:
                temporary = points[j]
                points[j] = points[j + 1]
                points[j + 1] = temporary

    # Calculate the area using the trapezoidal rule.
    area = 0.0

    for i in range(1, len(points)):
        width = points[i][0] - points[i - 1][0]
        average_height = (
            points[i][1] + points[i - 1][1]
        ) / 2

        area = area + width * average_height

    return area


def normalizeAUC(target_auc: float, reference_auc: float) -> float:
    """Divide the target area by the reference area."""

    if target_auc is None or reference_auc is None:
        return None

    if reference_auc == 0:
        return None

    return target_auc / reference_auc


def calculatePercentChange(value: float,baseline: float) -> float:
    """Calculate percentage change relative to the baseline."""

    if value is None or baseline is None:
        return None

    if baseline == 0:
        return None

    change = (value - baseline) / baseline * 100

    return change


def fmt(value: float) -> str:
    """Display a number or N/A when a result is unavailable."""

    if value is None:
        return "N/A"

    return f"{value:.4f}"


# ------------------------------------------------------------
# Website routes

@route
def index(state: State) -> Page:
    """Open the upload page."""

    return uploadPage(state)


@route
def uploadPage(state: State, error: str = "") -> Page:
    """Display the TXT file upload page."""

    content = [
        "Step 1: Upload TXT files",
        LineBreak()
    ]

    if error != "":
        content.append(error)
        content.append(LineBreak())

    content += [
        "Sample name:",
        TextBox("sample_name", ""),
        LineBreak(),
        FileUpload("file"),
        LineBreak(),
        Button("Add sample", addSpectrum),
        LineBreak(),
        "Uploaded samples:",
        LineBreak()
    ]

    for name in state.spectra:
        content.append(name)
        content.append(LineBreak())

    content.append(Button("Continue", referencePage))

    return Page(state, content)


@route
def addSpectrum(state: State, sample_name: str, file: bytes) -> Page:
    """Read a TXT file and add it to the uploaded samples."""

    if sample_name.strip() == "":
        return uploadPage(state, "Please enter a sample name.")

    sample_name = sample_name.strip()

    if sample_name in state.spectra:
        return uploadPage(state, "That sample name already exists.")

    if file is None or file == b"":
        return uploadPage(state, "Please upload a TXT file.")

    text = file.decode("utf-8")
    wavenumbers, intensities = parseSpectrumText(text)

    if len(wavenumbers) == 0:
        return uploadPage(
            state,
            "The file is empty or contains no valid data."
        )

    if len(wavenumbers) < 2:
        return uploadPage(
            state,
            "The file needs at least two data points."
        )

    new_spectrum = Spectrum(
        sample_name,
        wavenumbers,
        intensities
    )

    state.spectra[sample_name] = new_spectrum

    return uploadPage(state)


@route
def referencePage(state: State, error: str = "") -> Page:
    """Display the reference peak settings page."""

    if len(state.spectra) == 0:
        return uploadPage(
            state,
            "Upload at least one sample first."
        )

    content = [
        "Step 2: Reference peak",
        LineBreak()
    ]

    if error != "":
        content.append(error)
        content.append(LineBreak())

    content += [
        "Start (cm-1):",
        TextBox("ref_start", ""),
        LineBreak(),
        "End (cm-1):",
        TextBox("ref_end", ""),
        LineBreak(),
        "Signal type:",
        SelectBox(
            "signal_type",
            ["Absorbance", "Transmittance"],
            state.signal_type
        ),
        LineBreak(),
        Button("Save reference range", saveReference)
    ]

    return Page(state, content)


@route
def saveReference(state: State, ref_start: str,ref_end: str,signal_type: str) -> Page:
    """Save the reference peak range and signal type."""

    peak_range = parseRange(ref_start, ref_end)

    if peak_range is None:
        return referencePage(
            state,
            "Invalid reference range. Check your numbers."
        )

    state.reference_range = peak_range
    state.signal_type = signal_type

    return targetPage(state)


@route
def targetPage(state: State, error: str = "") -> Page:
    """Display the target peak settings page."""

    content = [
        "Step 3: Target peak(s)",
        LineBreak(),
        "Saved target ranges:",
        LineBreak()
    ]

    if error != "":
        content.append(error)
        content.append(LineBreak())

    for target_range in state.target_ranges:
        content.append(
            str(target_range[0]) + " - " + str(target_range[1])
        )
        content.append(LineBreak())

    content += [
        "Start (cm-1):",
        TextBox("target_start", ""),
        LineBreak(),
        "End (cm-1):",
        TextBox("target_end", ""),
        LineBreak(),
        Button("Add another target range", addTarget),
        Button("Continue", baselinePage)
    ]

    return Page(state, content)


@route
def addTarget(state: State, target_start: str, target_end: str) -> Page:
    """Save another target peak range."""

    peak_range = parseRange(target_start, target_end)

    if peak_range is None:
        return targetPage(state, "Invalid target range.")

    state.target_ranges.append(peak_range)

    return targetPage(state)


@route
def baselinePage(state: State, target_start: str = "", target_end: str = "", error: str = "") -> Page:
    """Save the final target range and display baseline selection."""

    # Save the last target range if the user entered one.
    if target_start != "" or target_end != "":
        peak_range = parseRange(target_start, target_end)

        if peak_range is None:
            return targetPage(state, "Invalid target range.")

        state.target_ranges.append(peak_range)

    if len(state.target_ranges) == 0:
        return targetPage(
            state,
            "Enter at least one target range."
        )

    content = [
        "Step 4: Select baseline sample",
        LineBreak()
    ]

    if error != "":
        content.append(error)
        content.append(LineBreak())

    names = []

    for name in state.spectra:
        names.append(name)

    content += [
        "Choose your baseline sample:",
        SelectBox("baseline_sample", names, names[0]),
        LineBreak(),
        Button("Calculate results", showResults)
    ]

    return Page(state, content)


@route
def showResults(state: State, baseline_sample: str) -> Page:
    """Calculate the AUCs and display the results."""

    if baseline_sample not in state.spectra:
        return baselinePage(
            state,
            error="Please select a valid baseline sample."
        )

    if len(state.reference_range) != 2:
        return referencePage(state, "Enter a reference range first.")

    if len(state.target_ranges) == 0:
        return targetPage(state, "Enter at least one target range.")

    state.baseline_sample = baseline_sample
    state.results = {}

    # Calculate reference and target AUCs for every sample.
    for sample_name, spectrum in state.spectra.items():

        reference_auc = calculateAUC(
            spectrum.wavenumbers,
            spectrum.intensities,
            state.reference_range
        )

        target_aucs = []
        normalized_values = []

        for target_range in state.target_ranges:

            target_auc = calculateAUC(
                spectrum.wavenumbers,
                spectrum.intensities,
                target_range
            )

            normalized_value = normalizeAUC(
                target_auc,
                reference_auc
            )

            target_aucs.append(target_auc)
            normalized_values.append(normalized_value)

        state.results[sample_name] = {
            "reference_auc": reference_auc,
            "target_aucs": target_aucs,
            "normalized": normalized_values,
            "percent_change": []
        }

    # Get the normalized values of the baseline sample.
    baseline_results = state.results[state.baseline_sample]
    baseline_values = baseline_results["normalized"]

    # Calculate percentage change for each sample.
    for sample_name in state.results:

        result = state.results[sample_name]
        percent_changes = []

        for i in range(len(result["normalized"])):

            value = result["normalized"][i]
            baseline_value = baseline_values[i]

            change = calculatePercentChange(
                value,
                baseline_value
            )

            percent_changes.append(change)

        result["percent_change"] = percent_changes

    # Display the results.
    content = [
        "Step 5: Analysis Results",
        LineBreak(),
        "Baseline sample: " + state.baseline_sample,
        LineBreak(),
        "Signal type: " + state.signal_type,
        LineBreak(),
        LineBreak()
    ]

    for sample_name in state.results:

        result = state.results[sample_name]

        content += [
            "Sample: " + sample_name,
            LineBreak(),
            "Reference AUC: " + fmt(result["reference_auc"]),
            LineBreak()
        ]

        for i in range(len(state.target_ranges)):

            target_range = state.target_ranges[i]

            content += [
                "Target range: "
                + str(target_range[0])
                + " - "
                + str(target_range[1]),
                LineBreak(),
                "Target AUC: "
                + fmt(result["target_aucs"][i]),
                LineBreak(),
                "Normalized value: "
                + fmt(result["normalized"][i]),
                LineBreak(),
                "Percentage change: "
                + fmt(result["percent_change"][i])
                + "%",
                LineBreak(),
                LineBreak()
            ]

    content += [
        Button("Edit settings", referencePage),
        Button("New analysis", newAnalysis)
    ]

    return Page(state, content)


@route
def newAnalysis(state: State) -> Page:
    """Clear the current analysis and return to the upload page."""

    state.spectra = {}
    state.reference_range = []
    state.target_ranges = []
    state.signal_type = "Absorbance"
    state.baseline_sample = ""
    state.results = {}

    return uploadPage(state)


# ------------------------------------------------------------
# Start the website

start_server(State({},[],[],"Absorbance","",{}))
