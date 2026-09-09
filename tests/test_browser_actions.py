import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from draft_tool.browser_actions import (
    _is_sku_price_hint,
    _requested_property_parts,
    _set_input_value,
    _configure_sku_image_via_picker,
    add_sale_dimensions,
    discover_sale_property_slots,
    fill_package_weights,
    fill_prop,
    fill_quotation_type,
    fill_sku_rows,
    match_sku_rows_by_specification,
    preview_result,
    probe_sku_image_capability,
    configure_sku_images,
    remove_unrequested_checkbox_values,
    safe_required_attribute_default,
    source_property_map,
)
from draft_tool.browser_navigation import dismiss_unexpected_popups


class BrowserActionTests(unittest.TestCase):
    @patch("draft_tool.browser_actions._picker_submit", return_value=True)
    @patch("draft_tool.browser_actions._picker_select_titles", return_value=1)
    @patch("draft_tool.browser_actions._close_picture_picker")
    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_sku_image_picker_uses_valid_css_locator(self, _sleep, _close, _select, _submit):
        page = MagicMock()
        row = MagicMock()
        add_button = MagicMock()
        row.ele.return_value = add_button
        frame = MagicMock()
        page.get_frame.return_value = frame

        self.assertTrue(_configure_sku_image_via_picker(page, row, Path("C:/tmp/red.jpg")))
        selector = row.ele.call_args.args[0]
        self.assertEqual(selector, "css:.sku-picture-content, .sku-picture-url")
        self.assertNotIn(", css:", selector)

    def test_discover_sale_property_slots_uses_spec_blocks(self):
        page = MagicMock()
        page.run_js.return_value = [
            {"index": 0, "placeholder": "请输入或选择颜色", "label": "颜色"},
            {"index": 1, "placeholder": "请输入规格", "label": "规格"},
        ]

        slots = discover_sale_property_slots(page)

        self.assertEqual(slots[1]["label"], "规格")
        self.assertIn("module-spec-decorator", page.run_js.call_args.args[0])

    @patch("draft_tool.browser_actions.add_sale_values", return_value=2)
    @patch("draft_tool.browser_actions.discover_sale_property_slots", return_value=[
        {"index": 0, "placeholder": "请输入或选择颜色", "label": "颜色"},
        {"index": 1, "placeholder": "请输入规格", "label": "规格"},
    ])
    def test_add_sale_dimensions_fills_two_distinct_property_slots(self, _discover, _add):
        model = {
            "dimensions": [
                {"name": "颜色", "values": ["莫兰绿", "豆沙紫"]},
                {"name": "规格", "values": ["标准版", "充电版"]},
            ]
        }

        result = add_sale_dimensions(MagicMock(), model)

        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["accepted_values"], 4)

    def test_unexpected_native_dialogs_are_dismissed(self):
        page = MagicMock()
        page.handle_alert.side_effect = ["提示", None]
        page.run_js.return_value = None

        dismissed = dismiss_unexpected_popups(page)

        self.assertEqual(dismissed, ["提示"])
        self.assertEqual(page.handle_alert.call_count, 2)
        page.run_js.assert_called_once()

    def test_unexpected_popup_dismissal_is_safe_without_native_dialog(self):
        page = MagicMock()
        page.handle_alert.side_effect = Exception("no alert")
        page.run_js.return_value = None

        dismissed = dismiss_unexpected_popups(page)

        self.assertEqual(dismissed, [])
        page.run_js.assert_called_once()

    def test_sku_image_capability_probe_is_read_only(self):
        page = MagicMock()
        page.run_js.return_value = {"supported": True, "scope": "sku_row", "controls": []}
        result = probe_sku_image_capability(page)
        self.assertTrue(result["supported"])
        self.assertEqual(result["scope"], "sku_row")
        self.assertEqual(page.run_js.call_count, 1)

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.read_sku_table_rows", return_value=[])
    def test_sku_image_configuration_uses_row_file_input(self, _read, _sleep):
        page = MagicMock()
        row = MagicMock()
        file_input = MagicMock()
        row.ele.return_value = file_input
        row.eles.side_effect = [[ ], [MagicMock()]]
        result = configure_sku_images(
            page,
            [{"sku_id": "1", "name": "红"}],
            {"1": Path("C:/tmp/red.jpg")},
            [row],
        )
        self.assertEqual(result["status"], "confirmed")
        file_input.input.assert_called_once()

    @patch("draft_tool.browser_actions.read_sku_table_rows", return_value=[])
    def test_multi_sku_image_configuration_never_guesses_row_order(self, _read):
        rows = [MagicMock(), MagicMock()]
        result = configure_sku_images(
            MagicMock(),
            [{"sku_id": "1", "name": "红"}, {"sku_id": "2", "name": "蓝"}],
            {"1": Path("C:/tmp/red.jpg"), "2": Path("C:/tmp/blue.jpg")},
            rows,
        )
        self.assertEqual(result["status"], "mapping_ambiguous")
        for row in rows:
            row.ele.assert_not_called()

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.time.time", side_effect=[0, 1, 9])
    @patch("draft_tool.browser_actions.read_sku_table_rows", return_value=[])
    def test_existing_row_image_is_not_upload_confirmation(self, _read, _time, _sleep):
        row = MagicMock()
        row.ele.return_value = MagicMock()
        row.eles.return_value = [MagicMock()]
        result = configure_sku_images(
            MagicMock(), [{"sku_id": "1", "name": "红"}],
            {"1": Path("C:/tmp/red.jpg")}, [row],
        )
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["failed"][0]["reason"], "image_preview_not_confirmed")

    @patch("draft_tool.browser_actions._configure_sku_image_via_picker", return_value=True)
    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.read_sku_table_rows", return_value=[])
    def test_sku_image_configuration_uses_add_button_picker(self, _read, _sleep, _picker):
        page = MagicMock()
        row = MagicMock()
        row.ele.return_value = None
        row.eles.side_effect = [[], [MagicMock()]]
        result = configure_sku_images(
            page,
            [{"sku_id": "1", "name": "红"}],
            {"1": Path("C:/tmp/red.jpg")},
            [row],
        )
        self.assertEqual(result["status"], "confirmed")
        _picker.assert_called_once()

    @patch("draft_tool.browser_actions._configure_sku_image_via_picker", return_value=False)
    @patch("draft_tool.browser_actions.read_sku_table_rows", return_value=[])
    def test_sku_image_add_button_picker_failure_is_fail_closed(self, _read, _picker):
        page = MagicMock()
        row = MagicMock()
        row.ele.return_value = None
        row.eles.return_value = []
        result = configure_sku_images(
            page,
            [{"sku_id": "1", "name": "红"}],
            {"1": Path("C:/tmp/red.jpg")},
            [row],
        )
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["failed"][0]["reason"], "picker_image_control_failed")

    def test_missing_ip_license_uses_seller_documented_safe_default(self):
        self.assertEqual(safe_required_attribute_default("是否IP授权"), "否")
        self.assertIsNone(safe_required_attribute_default("品牌"))

    def test_material_alias_matches_target_toy_material_label(self):
        page = MagicMock()
        page.run_js.return_value = [{"id": "1626126", "label": "玩具材质"}]
        self.assertEqual(source_property_map(page, {"材质": "塑料/塑胶"}), {
            "1626126": "塑料/塑胶"
        })

    def test_unlimited_audience_is_removed_when_specific_values_exist(self):
        self.assertEqual(_requested_property_parts("不限,女孩,男孩"), ["女孩", "男孩"])
        self.assertEqual(_requested_property_parts("不限"), ["不限"])

    def test_property_value_matching_is_discrete_and_keeps_slash_labels(self):
        from draft_tool.browser_actions import _property_values_match

        self.assertTrue(_property_values_match("女孩,男孩", ["女孩", "男孩"]))
        self.assertFalse(_property_values_match("男孩", ["男"]))
        self.assertEqual(_requested_property_parts("塑料/塑胶"), ["塑料/塑胶"])

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_conflicting_checkbox_prefill_is_removed(self, _sleep):
        page = MagicMock()
        page.run_js.side_effect = ["彩盒", ""]

        removed = remove_unrequested_checkbox_values(page, "21292", ["袋装"])

        self.assertEqual(removed, ["彩盒"])
        self.assertEqual(page.run_js.call_count, 2)

    def test_all_sku_price_paths_recognize_wholesale_price(self):
        self.assertTrue(_is_sku_price_hint("批发价"))
        self.assertTrue(_is_sku_price_hint("price"))
        self.assertFalse(_is_sku_price_hint("报价方式"))

    def test_sku_code_header_with_batch_setting_is_still_a_code_field(self):
        from draft_tool.browser_actions import _is_sku_code_hint

        self.assertTrue(_is_sku_code_hint("单品货号\n批量设置"))
        self.assertFalse(_is_sku_code_hint("SKU分类\n批量设置"))

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.selected_prop_value", return_value="请选择")
    @patch("draft_tool.browser_actions.click_best_visible_option")
    @patch("draft_tool.browser_actions.click_visible_text", return_value=False)
    def test_fill_prop_retries_delayed_select_options(
        self, _exact, best, _selected, _sleep
    ):
        best.side_effect = ["", "", "玩沙工具"]
        _selected.side_effect = ["请选择", "请选择", "玩沙工具"]
        page = MagicMock()
        box = MagicMock()
        field = MagicMock()
        box.attr.return_value = "select"
        box.ele.side_effect = lambda selector, timeout=1: (
            None if selector == "tag:select" else field
        )
        page.ele.return_value = box

        self.assertTrue(fill_prop(page, "168226675", "玩沙工具"))
        self.assertEqual(field.click.call_count, 3)
        field.input.assert_not_called()

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.selected_prop_value", return_value="女孩,男孩")
    @patch("draft_tool.browser_actions.click_best_visible_option", return_value="男孩")
    @patch("draft_tool.browser_actions.remove_unrequested_checkbox_values", return_value=[])
    def test_fill_prop_detects_checkbox_from_real_dom_boolean(
        self, _remove, _best, _selected, _sleep
    ):
        page = MagicMock()
        page.run_js.return_value = True
        box = MagicMock()
        field = MagicMock()
        field.attr.return_value = ""
        box.attr.return_value = "select"
        box.ele.side_effect = lambda selector, timeout=1: (
            None if selector == "tag:select" else field
        )
        page.ele.return_value = box

        self.assertTrue(fill_prop(page, "21292", "女孩,男孩"))
        _remove.assert_called_once_with(page, "21292", ["女孩", "男孩"])

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.selected_prop_value", return_value="")
    @patch("draft_tool.browser_actions.click_best_visible_option", return_value="")
    def test_non_custom_enum_is_not_filled_as_plain_text(self, _best, _selected, _sleep):
        page = MagicMock()
        box = MagicMock()
        field = MagicMock()
        box.attr.return_value = "select"
        field.attr.side_effect = lambda key: "请选择" if key == "placeholder" else ""
        box.ele.side_effect = lambda selector, timeout=1: None if selector == "tag:select" else field
        page.ele.return_value = box

        self.assertFalse(fill_prop(page, "1626126", "塑料/塑胶"))
        field.input.assert_not_called()

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.selected_prop_value", return_value="2019152202028992")
    @patch("draft_tool.browser_actions.click_best_visible_option", return_value="")
    def test_fill_prop_fills_plain_text_input_directly(self, _best, _selected, _sleep):
        page = MagicMock()
        box = MagicMock()
        field = MagicMock()
        box.attr.return_value = "input"
        box.ele.side_effect = lambda selector, timeout=1: None if selector == "tag:select" else field
        field.attr.return_value = "请输入"
        page.ele.return_value = box

        self.assertTrue(fill_prop(page, "100020141", "2019152202028992"))
        field.click.assert_not_called()
        field.input.assert_called_once_with("2019152202028992", clear=True)

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.selected_prop_value", return_value="否")
    @patch("draft_tool.browser_actions.click_best_visible_option", return_value="")
    def test_fill_prop_stops_after_search_input_commits(self, _best, _selected, _sleep):
        page = MagicMock()
        box = MagicMock()
        trigger = MagicMock()
        field = MagicMock()
        box.attr.return_value = "select"
        box.ele.side_effect = lambda selector, timeout=1: (
            None if selector == "tag:select"
            else trigger if "next-select-trigger" in selector
            else field
        )
        trigger.attr.return_value = "next-select-trigger next-has-search"
        field.attr.return_value = "请输入"
        page.ele.return_value = box

        self.assertTrue(fill_prop(page, "11683430", "否"))
        self.assertEqual(_best.call_count, 1)

    def test_set_input_value_passes_the_actual_previous_value_to_react_bridge(self):
        field = MagicMock()
        field.attr.return_value = ""
        _set_input_value(field, 1)
        field.input.assert_called_once_with("1", clear=True)
        self.assertEqual(field.run_js.call_args.args[-2:], ("1", ""))

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_uniform_weight_uses_single_batch_action(self, _sleep):
        page = MagicMock()
        module = MagicMock()
        batch_input = MagicMock()
        batch_submit = MagicMock()
        rows = [MagicMock() for _ in range(43)]
        module.eles.return_value = rows
        module.ele.side_effect = lambda selector, timeout=1: (
            batch_input if "batch-bar__input" in selector else batch_submit
        )
        page.ele.return_value = module
        page.run_js.return_value = ["1000"] * 43

        result = fill_package_weights(
            page, [{"weight_grams": 1000, "source": "collected"}]
        )

        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["filled"], 43)
        batch_input.input.assert_called_once_with("1000", clear=True)
        batch_submit.click.assert_called_once_with()
        for row in rows:
            row.eles.assert_not_called()

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_missing_weight_uses_1000g_default(self, _sleep):
        page = MagicMock()
        module = MagicMock()
        batch_input = MagicMock()
        batch_submit = MagicMock()
        module.eles.return_value = [MagicMock(), MagicMock()]
        module.ele.side_effect = lambda selector, timeout=1: (
            batch_input if "batch-bar__input" in selector else batch_submit
        )
        page.ele.return_value = module
        page.run_js.return_value = ["1000", "1000"]
        result = fill_package_weights(page, [], default_weight_grams=None)
        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["default_weight_grams"], 1000)
        batch_input.input.assert_called_once_with("1000", clear=True)

    def test_varying_keyed_weights_require_real_target_sku_ids(self):
        page = MagicMock()
        module = MagicMock()
        rows = [MagicMock(), MagicMock()]
        for row in rows:
            row.attr.return_value = ""
            row.eles.return_value = []
        module.eles.return_value = rows
        page.ele.return_value = module
        result = fill_package_weights(page, [
            {"sku_id": "A", "weight_grams": 100},
            {"sku_id": "B", "weight_grams": 200},
        ])
        self.assertEqual(result["status"], "mapping_ambiguous")
        self.assertEqual(result["filled"], 0)

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_varying_keyed_weights_use_merchant_code_as_safe_fallback(self, _sleep):
        page = MagicMock()
        module = MagicMock()
        rows = [MagicMock(), MagicMock()]
        codes = ["A", "B"]
        for row, code in zip(rows, codes):
            row.attr.return_value = ""
            code_input = MagicMock()
            code_input.attr.side_effect = lambda key, code=code: code if key == "value" else "单品货号"
            dimensions = [MagicMock(), MagicMock(), MagicMock()]
            for dimension in dimensions:
                dimension.attr.return_value = ""
            weight_input = MagicMock()
            state = {"value": ""}
            weight_input.attr.side_effect = lambda key, state=state: state["value"] if key == "value" else "重量"
            weight_input.input.side_effect = lambda value, clear=True, state=state: state.update(value=str(value))
            row.eles.side_effect = lambda selector, code_input=code_input, weight_input=weight_input, dimensions=dimensions: (
                [] if selector == 'css:input[type="hidden"]' else [*dimensions, weight_input, code_input]
            )
        module.eles.return_value = rows
        module.ele.return_value = None
        page.ele.return_value = module
        result = fill_package_weights(page, [
            {"sku_id": "A", "weight_grams": 100},
            {"sku_id": "B", "weight_grams": 200},
        ])
        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["expected_weights"], [100, 200])

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_target_platform_id_falls_back_to_matching_merchant_code(self, _sleep):
        page = MagicMock()
        module = MagicMock()
        rows = [MagicMock(), MagicMock()]
        for row, code, platform_id in zip(rows, ["A", "B"], ["target-1", "target-2"]):
            row.attr.side_effect = lambda key, platform_id=platform_id: platform_id if key == "data-sku-id" else ""
            hidden = MagicMock()
            hidden.attr.side_effect = lambda key, platform_id=platform_id: platform_id if key == "value" else "sku_id"
            code_input = MagicMock()
            code_input.attr.side_effect = lambda key, code=code: code if key == "value" else "单品货号"
            dimensions = [MagicMock(), MagicMock(), MagicMock()]
            for dimension in dimensions:
                dimension.attr.return_value = ""
            weight_input = MagicMock()
            state = {"value": ""}
            weight_input.attr.side_effect = lambda key, state=state: state["value"] if key == "value" else "重量"
            weight_input.input.side_effect = lambda value, clear=True, state=state: state.update(value=str(value))
            row.eles.side_effect = lambda selector, hidden=hidden, code_input=code_input, weight_input=weight_input, dimensions=dimensions: (
                [hidden] if selector == 'css:input[type="hidden"]' else [*dimensions, weight_input, code_input]
            )
        module.eles.return_value = rows
        module.ele.return_value = None
        page.ele.return_value = module

        result = fill_package_weights(page, [
            {"sku_id": "A", "weight_grams": 100},
            {"sku_id": "B", "weight_grams": 200},
        ])

        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["expected_weights"], [100, 200])

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_missing_sku_weight_uses_default_without_discarding_collected_weights(self, _sleep):
        page = MagicMock()
        module = MagicMock()
        rows = [MagicMock(), MagicMock(), MagicMock()]
        for row, code in zip(rows, ["A", "B", "C"]):
            row.attr.return_value = ""
            code_input = MagicMock()
            code_input.attr.side_effect = lambda key, code=code: code if key == "value" else "单品货号"
            dimensions = [MagicMock(), MagicMock(), MagicMock()]
            for dimension in dimensions:
                dimension.attr.return_value = ""
            weight_input = MagicMock()
            state = {"value": ""}
            weight_input.attr.side_effect = lambda key, state=state: state["value"] if key == "value" else "重量"
            weight_input.input.side_effect = lambda value, clear=True, state=state: state.update(value=str(value))
            row.eles.side_effect = lambda selector, code_input=code_input, weight_input=weight_input, dimensions=dimensions: (
                [] if selector == 'css:input[type="hidden"]' else [*dimensions, weight_input, code_input]
            )
        module.eles.return_value = rows
        module.ele.return_value = None
        page.ele.return_value = module

        result = fill_package_weights(page, [
            {"sku_id": "A", "weight_grams": 100},
            {"sku_id": "B", "weight_grams": 200},
        ])

        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["expected_weights"], [100, 200, 1000])

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_varying_weights_map_by_logistics_spec_cell(self, _sleep):
        page = MagicMock()
        module = MagicMock()
        rows = [MagicMock(), MagicMock()]
        specs = ["【芭比粉】医生收纳盒42件套", "【芭比粉】医生收纳盒65件套"]
        for row, spec in zip(rows, specs):
            row.attr.return_value = ""
            spec_node = MagicMock()
            spec_node.text = spec
            dimensions = [MagicMock(), MagicMock(), MagicMock()]
            for dimension in dimensions:
                dimension.attr.return_value = ""
            weight_input = MagicMock()
            state = {"value": ""}
            weight_input.attr.side_effect = lambda key, state=state: state["value"] if key == "value" else "重量"
            weight_input.input.side_effect = lambda value, clear=True, state=state: state.update(value=str(value))

            def eles(selector, spec_node=spec_node, dimensions=dimensions, weight_input=weight_input):
                if selector == 'css:input[type="hidden"]':
                    return []
                if selector == 'css:.sku-field-prop':
                    return [spec_node]
                if selector == 'css:input:not([type="hidden"])':
                    return [*dimensions, weight_input]
                return []

            row.eles.side_effect = eles
        module.eles.return_value = rows
        module.ele.return_value = None
        page.ele.return_value = module

        result = fill_package_weights(
            page,
            [{"sku_id": "A", "weight_grams": 316}, {"sku_id": "B", "weight_grams": 637}],
            source_skus=[
                {"sku_id": "A", "properties": {"颜色": "【芭比粉】医生收纳盒42件套"}},
                {"sku_id": "B", "properties": {"颜色": "【芭比粉】医生收纳盒65件套"}},
            ],
        )

        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["expected_weights"], [316, 637])

    def test_ambiguous_logistics_spec_does_not_map_varying_weights(self):
        page = MagicMock()
        module = MagicMock()
        rows = [MagicMock(), MagicMock()]
        for row in rows:
            row.attr.return_value = ""
            spec_node = MagicMock()
            spec_node.text = "【芭比粉】医生收纳盒42件套"
            row.eles.side_effect = lambda selector, spec_node=spec_node: (
                [] if selector == 'css:input[type="hidden"]'
                else [spec_node] if selector == 'css:.sku-field-prop'
                else []
            )
        module.eles.return_value = rows
        module.ele.return_value = None
        page.ele.return_value = module

        result = fill_package_weights(
            page,
            [{"sku_id": "A", "weight_grams": 316}, {"sku_id": "B", "weight_grams": 637}],
            source_skus=[
                {"sku_id": "A", "properties": {"颜色": "【芭比粉】医生收纳盒42件套"}},
                {"sku_id": "B", "properties": {"颜色": "【芭比粉】医生收纳盒42件套"}},
            ],
        )

        self.assertEqual(result["status"], "mapping_ambiguous")

    def test_duplicate_merchant_codes_do_not_map_varying_weights(self):
        page = MagicMock()
        module = MagicMock()
        rows = [MagicMock(), MagicMock()]
        for row in rows:
            row.attr.return_value = ""
            code = MagicMock()
            code.attr.side_effect = lambda key: "A" if key == "value" else "单品货号"
            row.eles.side_effect = lambda selector, code=code: (
                [] if selector == 'css:input[type="hidden"]' else [code]
            )
        module.eles.return_value = rows
        page.ele.return_value = module
        result = fill_package_weights(page, [
            {"sku_id": "A", "weight_grams": 100},
            {"sku_id": "B", "weight_grams": 200},
        ])
        self.assertEqual(result["status"], "mapping_ambiguous")
        self.assertEqual(result["reason"], "target_row_identity_mismatch")

    def test_preview_reports_invalid_sku_instead_of_success(self):
        result = preview_result(
            {"source_count": 2, "valid": True},
            {
                "sku_dimensions": {"status": "filled"},
                "sku_validation": {"valid": False},
                "quotation_type": {"required": True, "status": "selected", "minimum_order_filled": True},
                "package_dimensions": {"status": "skipped"},
            },
            {"errors": []},
        )
        self.assertEqual(result, "preview_invalid")

    def test_preview_reports_page_validation_errors(self):
        result = preview_result(
            {"source_count": 0},
            {"quotation_type": {"required": False}, "package_dimensions": {"status": "skipped"}},
            {"errors": ["1 错误 请填写批发价"]},
        )
        self.assertEqual(result, "preview_invalid")

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_multiple_sku_prices_select_spec_quotation(self, _sleep):
        page = MagicMock()
        page.run_js.side_effect = [True, True, {
            "value": "2", "ariaValue": "2", "invalid": False, "localError": False,
        }]
        begin_amount = MagicMock()
        begin_amount.attr.return_value = ""
        title = MagicMock()
        page.ele.side_effect = [begin_amount, title]

        result = fill_quotation_type(page, [5.2, 12.6], "2件起批")

        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["mode"], "sku")
        self.assertEqual(result["distinct_prices"], 2)
        self.assertEqual(result["minimum_order"], 2)
        self.assertTrue(result["minimum_order_filled"])

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.read_sku_table_rows")
    @patch("draft_tool.browser_actions.discover_sku_table")
    def test_sku_rows_receive_their_own_prices(self, discover, _read, _sleep):
        discover.return_value = {"selected": {"row_count": 2}}
        _read.side_effect = [
            [
                {"text": "红色", "properties": {"颜色": "红色"}},
                {"text": "蓝色", "properties": {"颜色": "蓝色"}},
            ],
            [],
            [],
        ]
        page = MagicMock()
        rows = []
        price_inputs = []
        for _ in range(2):
            price_input, stock_input, code_input = MagicMock(), MagicMock(), MagicMock()
            for item, hint in (
                (price_input, "价格"),
                (stock_input, "可售数量"),
                (code_input, "单品货号"),
            ):
                item.attr.side_effect = lambda key, hint=hint: hint if key == "data-codex-field" else ""
            row = MagicMock()
            row.eles.return_value = [price_input, stock_input, code_input]
            rows.append(row)
            price_inputs.append(price_input)
        page.eles.return_value = rows

        fill_sku_rows(page, [
            {"name": "红色", "properties": {"颜色": "红色"}, "price": 5.2, "stock": 3, "sku_id": "1"},
            {"name": "蓝色", "properties": {"颜色": "蓝色"}, "price": 12.6, "stock": 4, "sku_id": "2"},
        ])

        price_inputs[0].input.assert_called_once_with("5.2", clear=True)
        price_inputs[1].input.assert_called_once_with("12.6", clear=True)

    def test_sku_rows_match_reordered_target_by_specification(self):
        source = [
            {"name": "红色", "properties": {"颜色": "红色"}},
            {"name": "蓝色", "properties": {"颜色": "蓝色"}},
        ]
        rendered = [
            {"text": "蓝色", "properties": {"颜色": "蓝色"}},
            {"text": "红色", "properties": {"颜色": "红色"}},
        ]
        self.assertEqual(match_sku_rows_by_specification(source, rendered), [1, 0])

    def test_sku_row_matching_does_not_use_substrings(self):
        source = [{"name": "大", "properties": {"尺寸": "大"}}]
        rendered = [{"text": "大号", "properties": {"尺寸": "大号"}}]
        self.assertIsNone(match_sku_rows_by_specification(source, rendered))

    def test_sku_rows_return_no_mapping_for_ambiguous_target(self):
        source = [
            {"name": "红色", "properties": {"颜色": "红色"}},
            {"name": "蓝色", "properties": {"颜色": "蓝色"}},
        ]
        rendered = [{"text": "未加载规格", "properties": {}}] * 2
        self.assertIsNone(match_sku_rows_by_specification(source, rendered))

    @patch("draft_tool.browser_actions.read_sku_table_rows", return_value=[])
    @patch("draft_tool.browser_actions.discover_sku_table")
    def test_multi_sku_fill_stops_when_target_specifications_are_unreadable(
        self, discover, _read
    ):
        discover.return_value = {"selected": {"row_count": 2}}
        page = MagicMock()
        page.eles.return_value = [MagicMock(), MagicMock()]

        result = fill_sku_rows(page, [
            {"name": "红色", "properties": {"颜色": "红色"}, "price": 5, "stock": 1},
            {"name": "蓝色", "properties": {"颜色": "蓝色"}, "price": 6, "stock": 1},
        ])

        self.assertEqual(result["mapping"], "ambiguous")
        self.assertEqual(result["count"], 0)
        for row in page.eles.return_value:
            row.eles.assert_not_called()

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    @patch("draft_tool.browser_actions.read_sku_table_rows", return_value=[])
    @patch("draft_tool.browser_actions.discover_sku_table")
    def test_wholesale_price_and_sku_category_are_distinguished(self, discover, _read, _sleep):
        discover.return_value = {"selected": {"row_count": 1}}
        page = MagicMock()
        wholesale, category, stock, code = [MagicMock() for _ in range(4)]
        hints = {
            id(wholesale): "批发价",
            id(category): "SKU分类 批量设置",
            id(stock): "可售数量",
            id(code): "单品货号",
        }
        for item in (wholesale, category, stock, code):
            item.attr.side_effect = lambda key, item=item: hints[id(item)] if key == "data-codex-field" else ""
        row = MagicMock()
        row.eles.return_value = [wholesale, category, stock, code]
        page.eles.side_effect = [[row], [row], [row]]
        fill_sku_rows(page, [{"price": 7.5, "stock": 8, "sku_id": "SKU-1"}])
        wholesale.input.assert_called_once_with("7.5", clear=True)
        code.input.assert_called_once_with("SKU-1", clear=True)
        category.input.assert_not_called()


if __name__ == "__main__":
    unittest.main()
