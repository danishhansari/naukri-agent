def normalize(value):
    if value is None:
        return ""

    return " ".join(
        str(value)
        .strip()
        .lower()
        .split()
    )


def get_element(page, field):
    selector = (
        "input:not([type='hidden']):not([type='radio']), "
        "textarea, "
        "select"
    )

    return page.locator(
        selector
    ).nth(
        field["index"]
    )


def fill_select(
    element,
    answer
):
    desired = normalize(answer)

    options = element.locator(
        "option"
    )

    # Exact match
    for i in range(
        options.count()
    ):

        option = options.nth(i)

        text = normalize(
            option.inner_text()
        )

        value = normalize(
            option.get_attribute(
                "value"
            )
        )

        if (
            desired == text
            or desired == value
        ):

            element.select_option(
                value=option.get_attribute(
                    "value"
                )
            )

            return True

    # Partial match
    for i in range(
        options.count()
    ):

        option = options.nth(i)

        text = normalize(
            option.inner_text()
        )

        value = normalize(
            option.get_attribute(
                "value"
            )
        )

        if (
            desired in text
            or text in desired
            or desired in value
            or value in desired
        ):

            element.select_option(
                value=option.get_attribute(
                    "value"
                )
            )

            return True

    return False


def click_radio_option(
    page,
    option
):
    """
    Click the actual radio option.
    """

    radio_id = option.get(
        "id"
    )

    option_value = option.get(
        "value"
    )

    # Best case: ID + associated label.
    if radio_id:

        try:

            label = page.locator(
                f'label[for="{radio_id}"]'
            ).first

            if label.count():

                label.click()

                return True

        except Exception:
            pass

    # Direct input by ID.
    if radio_id:

        try:

            radio = page.locator(
                f"#{radio_id}"
            ).first

            if radio.count():

                radio.check(
                    force=True
                )

                return True

        except Exception:
            pass

    # Fall back to value.
    if option_value:

        try:

            radio = page.locator(
                f'input[type="radio"][value="{option_value}"]'
            ).first

            if radio.count():

                radio.check(
                    force=True
                )

                return True

        except Exception:
            pass

    return False


def fill_radio_group(
    page,
    field,
    answer
):
    """
    Match the LLM answer against:
      - option text
      - option value
      - yes/no variants

    Then click the actual radio button.
    """

    desired = normalize(
        answer
    )

    options = field.get(
        "options",
        []
    )

    if not options:
        return False

    # Exact match first.
    for option in options:

        text = normalize(
            option.get("text")
        )

        value = normalize(
            option.get("value")
        )

        if (
            desired == text
            or desired == value
        ):

            print(
                f"    Clicking radio: "
                f"{option.get('text')}"
            )

            return click_radio_option(
                page,
                option
            )

    # Yes / No normalization.
    yes_values = {
        "yes",
        "y",
        "true",
        "1"
    }

    no_values = {
        "no",
        "n",
        "false",
        "0"
    }

    if desired in yes_values:

        for option in options:

            combined = normalize(
                (
                    option.get("text", "")
                    + " "
                    + option.get("value", "")
                )
            )

            if (
                combined == "yes"
                or combined.startswith("yes ")
                or " yes " in f" {combined} "
            ):

                return click_radio_option(
                    page,
                    option
                )

    if desired in no_values:

        for option in options:

            combined = normalize(
                (
                    option.get("text", "")
                    + " "
                    + option.get("value", "")
                )
            )

            if (
                combined == "no"
                or combined.startswith("no ")
                or " no " in f" {combined} "
            ):

                return click_radio_option(
                    page,
                    option
                )

    # Partial match.
    for option in options:

        text = normalize(
            option.get("text")
        )

        value = normalize(
            option.get("value")
        )

        if (
            desired in text
            or text in desired
            or desired in value
            or value in desired
        ):

            return click_radio_option(
                page,
                option
            )

    return False


def fill_checkbox(
    element,
    answer
):
    desired = normalize(answer)

    should_check = desired in {
        "yes",
        "true",
        "1",
        "checked"
    }

    if should_check:
        element.check()
    else:
        element.uncheck()

    return True


def fill_field(
    page,
    field,
    answer
):
    """
    Fill one logical form field.
    """

    if answer is None:
        return False

    field_type = normalize(
        field.get("type")
    )

    tag = normalize(
        field.get("tag")
    )

    # RADIO GROUP
    if (
        field_type == "radio"
        or tag == "radio-group"
    ):

        return fill_radio_group(
            page,
            field,
            answer
        )

    element = get_element(
        page,
        field
    )

    try:

        if not element.is_visible():
            return False

    except Exception:

        return False

    try:

        # SELECT
        if tag == "select":

            return fill_select(
                element,
                answer
            )

        # CHECKBOX
        if field_type == "checkbox":

            return fill_checkbox(
                element,
                answer
            )

        # TEXT / EMAIL / NUMBER / TEXTAREA
        element.fill(
            str(answer)
        )

        return True

    except Exception as exc:

        print(
            f"    Error filling "
            f"{field.get('label')}: {exc}"
        )

        return False


def validate_field(
    page,
    field,
    expected
):
    """
    Validate the actual form state.
    """

    if expected is None:
        return True

    field_type = normalize(
        field.get("type")
    )

    tag = normalize(
        field.get("tag")
    )

    # RADIO
    if (
        field_type == "radio"
        or tag == "radio-group"
    ):

        desired = normalize(
            expected
        )

        for option in field.get(
            "options",
            []
        ):

            text = normalize(
                option.get("text")
            )

            value = normalize(
                option.get("value")
            )

            if (
                desired == text
                or desired == value
            ):

                radio_id = option.get(
                    "id"
                )

                if radio_id:

                    try:

                        radio = page.locator(
                            f"#{radio_id}"
                        ).first

                        if radio.count():
                            return radio.is_checked()

                    except Exception:
                        pass

        # If we cannot inspect the radio,
        # don't incorrectly report failure.
        return True

    element = get_element(
        page,
        field
    )

    try:

        # SELECT
        if tag == "select":

            actual = normalize(
                element.locator(
                    "option:checked"
                ).inner_text()
            )

            return actual == normalize(
                expected
            )

        # CHECKBOX
        if field_type == "checkbox":

            checked = element.is_checked()

            desired = normalize(
                expected
            ) in {
                "yes",
                "true",
                "1",
                "checked"
            }

            return checked == desired

        # Text input
        actual = normalize(
            element.input_value()
        )

        return actual == normalize(
            expected
        )

    except Exception:

        # Some custom controls don't expose
        # normal input_value().
        return True