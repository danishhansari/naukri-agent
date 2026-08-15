from collections import defaultdict


def safe_attr(element, name):
    try:
        return element.get_attribute(name) or ""
    except Exception:
        return ""


def clean_text(value):
    if not value:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def get_label_for_input(page, element):
    """
    Find the human-readable label associated with an input.
    """

    field_id = safe_attr(element, "id")

    # 1. label[for="input-id"]
    if field_id:
        try:
            label = page.locator(
                f'label[for="{field_id}"]'
            ).first

            if label.count():
                text = clean_text(
                    label.inner_text()
                )

                if text:
                    return text
        except Exception:
            pass

    # 2. Input wrapped inside <label>
    try:
        parent_label = element.locator(
            "xpath=ancestor::label[1]"
        ).first

        if parent_label.count():
            text = clean_text(
                parent_label.inner_text()
            )

            if text:
                return text
    except Exception:
        pass

    # 3. aria-label
    aria = safe_attr(
        element,
        "aria-label"
    )

    if aria:
        return clean_text(aria)

    # 4. placeholder
    placeholder = safe_attr(
        element,
        "placeholder"
    )

    if placeholder:
        return clean_text(placeholder)

    return ""


def get_parent_question_text(
    page,
    element
):
    """
    For radio/checkbox/custom controls, the question
    is often somewhere in the parent container.
    """

    candidates = []

    # Try several parent levels.
    for level in range(1, 5):

        try:

            parent = element

            for _ in range(level):
                parent = parent.locator("..")

            if not parent.count():
                continue

            text = clean_text(
                parent.inner_text()
            )

            if text and len(text) < 1000:
                candidates.append(text)

        except Exception:
            continue

    if not candidates:
        return ""

    # Prefer the shortest useful parent text.
    candidates.sort(
        key=len
    )

    return candidates[0]


def get_radio_question(
    page,
    element
):
    """
    Try to find the actual question for a radio group.
    """

    # aria-labelledby
    labelled_by = safe_attr(
        element,
        "aria-labelledby"
    )

    if labelled_by:

        parts = []

        for element_id in labelled_by.split():

            try:

                locator = page.locator(
                    f"#{element_id}"
                ).first

                if locator.count():

                    text = clean_text(
                        locator.inner_text()
                    )

                    if text:
                        parts.append(text)

            except Exception:
                pass

        if parts:
            return clean_text(
                " ".join(parts)
            )

    # aria-label
    aria = safe_attr(
        element,
        "aria-label"
    )

    if aria:
        return clean_text(aria)

    # Fieldset legend
    try:

        parent = element.locator(
            "xpath=ancestor::fieldset[1]"
        ).first

        if parent.count():

            legend = parent.locator(
                "legend"
            ).first

            if legend.count():

                text = clean_text(
                    legend.inner_text()
                )

                if text:
                    return text

    except Exception:
        pass

    # Parent container
    return get_parent_question_text(
        page,
        element
    )


def get_radio_option_text(
    page,
    element
):
    """
    Get the text corresponding to an individual
    radio button.
    """

    field_id = safe_attr(
        element,
        "id"
    )

    # label[for]
    if field_id:

        try:

            label = page.locator(
                f'label[for="{field_id}"]'
            ).first

            if label.count():

                text = clean_text(
                    label.inner_text()
                )

                if text:
                    return text

        except Exception:
            pass

    # Wrapped label
    try:

        parent_label = element.locator(
            "xpath=ancestor::label[1]"
        ).first

        if parent_label.count():

            text = clean_text(
                parent_label.inner_text()
            )

            if text:
                return text

    except Exception:
        pass

    # aria-label
    aria = safe_attr(
        element,
        "aria-label"
    )

    if aria:
        return clean_text(aria)

    # value
    value = safe_attr(
        element,
        "value"
    )

    return clean_text(value)


def extract_radio_groups(page):
    """
    Build logical radio groups.

    Instead of:

        radio 1
        radio 2

    return:

        question:
            Are you willing to relocate?

        options:
            Yes
            No
    """

    radios = page.locator(
        'input[type="radio"]'
    )

    count = radios.count()

    groups = {}

    for i in range(count):

        radio = radios.nth(i)

        try:
            if not radio.is_visible():
                continue
        except Exception:
            continue

        name = safe_attr(
            radio,
            "name"
        )

        # Some sites don't give radios a name.
        # Fall back to parent/question text.
        question = get_radio_question(
            page,
            radio
        )

        group_key = (
            name
            if name
            else f"question::{question}"
        )

        if group_key not in groups:

            groups[group_key] = {
                "question_id":
                    f"radio_{len(groups)}",

                "tag": "radio-group",

                "type": "radio",

                "name": name,

                "label": question,

                "required": False,

                "options": []
            }

        option_text = get_radio_option_text(
            page,
            radio
        )

        option_value = safe_attr(
            radio,
            "value"
        )

        radio_id = safe_attr(
            radio,
            "id"
        )

        groups[group_key][
            "options"
        ].append({
            "text": option_text,
            "value": option_value,
            "id": radio_id,
            "index": i
        })

        # required
        try:
            if radio.is_required():
                groups[group_key][
                    "required"
                ] = True
        except Exception:
            pass

    return list(
        groups.values()
    )


def extract_standard_fields(page):
    """
    Extract non-radio fields.
    """

    fields = []

    selector = (
        "input:not([type='hidden']):not([type='radio']), "
        "textarea, "
        "select"
    )

    elements = page.locator(
        selector
    )

    count = elements.count()

    for i in range(count):

        element = elements.nth(i)

        try:
            if not element.is_visible():
                continue
        except Exception:
            continue

        tag = ""

        try:
            tag = element.evaluate(
                "(el) => el.tagName.toLowerCase()"
            )
        except Exception:
            continue

        field_type = safe_attr(
            element,
            "type"
        ).lower()

        if not field_type:
            field_type = tag

        field_id = safe_attr(
            element,
            "id"
        )

        name = safe_attr(
            element,
            "name"
        )

        placeholder = safe_attr(
            element,
            "placeholder"
        )

        aria = safe_attr(
            element,
            "aria-label"
        )

        label = get_label_for_input(
            page,
            element
        )

        if not label:
            label = aria

        if not label:
            label = placeholder

        if not label:
            label = name

        options = []

        if tag == "select":

            try:

                option_elements = element.locator(
                    "option"
                )

                for j in range(
                    option_elements.count()
                ):

                    option = (
                        option_elements.nth(j)
                    )

                    text = clean_text(
                        option.inner_text()
                    )

                    value = safe_attr(
                        option,
                        "value"
                    )

                    if text:
                        options.append({
                            "text": text,
                            "value": value
                        })

            except Exception:
                pass

        required = False

        try:
            required = element.is_required()
        except Exception:
            required = bool(
                safe_attr(
                    element,
                    "required"
                )
            )

        fields.append({
            "question_id":
                f"field_{i}",

            "index":
                i,

            "tag":
                tag,

            "type":
                field_type,

            "id":
                field_id,

            "name":
                name,

            "label":
                clean_text(label),

            "placeholder":
                placeholder,

            "required":
                required,

            "options":
                options
        })

    return fields


def extract_form_fields(page):
    """
    Main parser.

    Returns:
      - normal fields
      - logical radio groups
    """

    fields = []

    standard_fields = (
        extract_standard_fields(page)
    )

    radio_groups = (
        extract_radio_groups(page)
    )

    fields.extend(
        standard_fields
    )

    # Give radio groups their own IDs.
    for group in radio_groups:

        group["question_id"] = (
            f"radio_{len(fields)}"
        )

        fields.append(group)

    return fields


def extract_page_text(
    page,
    max_length=12000
):
    try:

        text = page.locator(
            "body"
        ).inner_text(
            timeout=5000
        )

        return text[:max_length]

    except Exception:
        return ""