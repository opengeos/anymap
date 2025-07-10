"""MapLibre widget classes for UI components.

This module contains the widget classes that support the MapLibreMap implementation,
including layer management, styling, and container widgets.

Classes:
    CustomWidget: Generic expansion panel widget with dynamic content management.
    Container: Container widget for map display with optional sidebar.
    LayerStyleWidget: Interactive widget for styling map layers.
    LayerManagerWidget: Widget for managing map layers (visibility, opacity, removal).

These classes were extracted from maplibre.py to improve code organization
and maintainability.
"""

from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

import ipyvuetify as v
import ipywidgets as widgets

if TYPE_CHECKING:
    from .maplibre import MapLibreMap


class CustomWidget(v.ExpansionPanels):
    """
    A custom expansion panel widget with dynamic widget management.

    This widget allows for the creation of an expandable panel with a customizable header
    and dynamic content. Widgets can be added, removed, or replaced in the content box.

    Attributes:
        content_box (widgets.VBox): A container for holding the widgets displayed in the panel.
        panel (v.ExpansionPanel): The main expansion panel containing the header and content.
    """

    def __init__(
        self,
        widget: Optional[Union[widgets.Widget, List[widgets.Widget]]] = None,
        widget_icon: str = "mdi-tools",
        close_icon: str = "mdi-close",
        label: str = "My Tools",
        background_color: str = "#f5f5f5",
        height: str = "40px",
        expanded: bool = True,
        host_map: Optional[Any] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the CustomWidget.

        Args:
            widget (Optional[Union[widgets.Widget, List[widgets.Widget]]]): Initial widget(s) to display in the content box.
            widget_icon (str): Icon for the header. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            close_icon (str): Icon for the close button. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            background_color (str): Background color of the header. Defaults to "#f5f5f5".
            label (str): Text label for the header. Defaults to "My Tools".
            height (str): Height of the header. Defaults to "40px".
            expanded (bool): Whether the panel is expanded by default. Defaults to True.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """
        # Wrap content in a mutable VBox
        self.content_box = widgets.VBox()
        self.host_map = host_map
        if widget:
            if isinstance(widget, (list, tuple)):
                self.content_box.children = widget
            else:
                self.content_box.children = [widget]

        # Close icon button
        close_btn = v.Btn(
            icon=True,
            small=True,
            class_="ma-0",
            style_="min-width: 24px; width: 24px;",
            children=[v.Icon(children=[close_icon])],
        )
        close_btn.on_event("click", self._handle_close)

        header = v.ExpansionPanelHeader(
            style_=f"height: {height}; min-height: {height}; background-color: {background_color};",
            children=[
                v.Row(
                    align="center",
                    class_="d-flex flex-grow-1 align-center",
                    children=[
                        v.Icon(children=[widget_icon], class_="ml-1"),
                        v.Spacer(),  # push title to center
                        v.Html(tag="span", children=[label], class_="text-subtitle-2"),
                        v.Spacer(),  # push close to right
                        close_btn,
                        v.Spacer(),
                    ],
                )
            ],
        )

        self.panel = v.ExpansionPanel(
            children=[
                header,
                v.ExpansionPanelContent(children=[self.content_box]),
            ]
        )

        super().__init__(
            children=[self.panel],
            v_model=[0] if expanded else [],
            multiple=True,
            *args,
            **kwargs,
        )

    def _handle_close(self, widget=None, event=None, data=None):
        """Calls the on_close callback if provided."""

        if self.host_map is not None:
            self.host_map.remove_from_sidebar(self)
        # self.close()

    def add_widget(self, widget: widgets.Widget) -> None:
        """
        Adds a widget to the content box.

        Args:
            widget (widgets.Widget): The widget to add to the content box.
        """
        self.content_box.children += (widget,)

    def remove_widget(self, widget: widgets.Widget) -> None:
        """
        Removes a widget from the content box.

        Args:
            widget (widgets.Widget): The widget to remove from the content box.
        """
        self.content_box.children = tuple(
            w for w in self.content_box.children if w != widget
        )

    def set_widgets(self, widgets_list: List[widgets.Widget]) -> None:
        """
        Replaces all widgets in the content box.

        Args:
            widgets_list (List[widgets.Widget]): A list of widgets to set as the content of the content box.
        """
        self.content_box.children = widgets_list


class Container(v.Container):
    """
    A container widget for displaying a map with an optional sidebar.

    This class creates a layout with a map on the left and a sidebar on the right.
    The sidebar can be toggled on or off and can display additional content.

    Attributes:
        sidebar_visible (bool): Whether the sidebar is visible.
        min_width (int): Minimum width of the sidebar in pixels.
        max_width (int): Maximum width of the sidebar in pixels.
        map_container (v.Col): The container for the map.
        sidebar_content_box (widgets.VBox): The container for the sidebar content.
        toggle_icon (v.Icon): The icon for the toggle button.
        toggle_btn (v.Btn): The button to toggle the sidebar.
        sidebar (v.Col): The container for the sidebar.
        row (v.Row): The main layout row containing the map and sidebar.
    """

    def __init__(
        self,
        host_map: Optional[Any] = None,
        sidebar_visible: bool = True,
        min_width: int = 250,
        max_width: int = 300,
        sidebar_content: Optional[Union[widgets.VBox, List[widgets.Widget]]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the Container widget.

        Args:
            host_map (Optional[Any]): The map object to display in the container. Defaults to None.
            sidebar_visible (bool): Whether the sidebar is visible. Defaults to True.
            min_width (int): Minimum width of the sidebar in pixels. Defaults to 250.
            max_width (int): Maximum width of the sidebar in pixels. Defaults to 300.
            sidebar_content (Optional[Union[widgets.VBox, List[widgets.Widget]]]):
                The content to display in the sidebar. Defaults to None.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """
        self.sidebar_visible = sidebar_visible
        self.min_width = min_width
        self.max_width = max_width
        self.host_map = host_map
        self.sidebar_widgets = {}

        # Map display container (left column)
        self.map_container = v.Col(
            class_="pa-1",
            style_="flex-grow: 1; flex-shrink: 1; flex-basis: 0;",
        )
        self.map_container.children = [host_map or self.create_map()]

        # Sidebar content container (mutable VBox)
        self.sidebar_content_box = widgets.VBox()
        if sidebar_content:
            self.set_sidebar_content(sidebar_content)

        # Toggle button
        if sidebar_visible:
            self.toggle_icon = v.Icon(children=["mdi-chevron-right"])
        else:
            self.toggle_icon = v.Icon(children=["mdi-chevron-left"])  # default icon
        self.toggle_btn = v.Btn(
            icon=True,
            children=[self.toggle_icon],
            style_="width: 48px; height: 48px; min-width: 48px;",
        )
        self.toggle_btn.on_event("click", self.toggle_sidebar)

        # Settings icon
        self.settings_icon = v.Icon(children=["mdi-wrench"])
        self.settings_btn = v.Btn(
            icon=True,
            children=[self.settings_icon],
            style_="width: 36px; height: 36px;",
        )
        self.settings_btn.on_event("click", self.toggle_width_slider)

        # Sidebar controls row (toggle + settings)
        self.sidebar_controls = v.Row(
            class_="ma-0 pa-0", children=[self.toggle_btn, self.settings_btn]
        )

        # Sidebar width slider (initially hidden)
        self.width_slider = widgets.IntSlider(
            value=self.max_width,
            min=200,
            max=1000,
            step=10,
            description="Width:",
            continuous_update=True,
        )
        self.width_slider.observe(self.on_width_change, names="value")

        self.settings_widget = CustomWidget(
            self.width_slider,
            widget_icon="mdi-cog",
            label="Sidebar Settings",
            host_map=self.host_map,
        )

        # Sidebar (right column)
        self.sidebar = v.Col(class_="pa-1", style_="overflow-y: hidden;")
        self.update_sidebar_content()

        # Main layout row
        self.row = v.Row(
            class_="d-flex flex-nowrap",
            children=[self.map_container, self.sidebar],
        )

        super().__init__(fluid=True, children=[self.row], *args, **kwargs)

    def create_map(self) -> Any:
        """
        Creates a default map object.

        Returns:
            Any: A default map object.
        """
        from .maplibre import MapLibreMap

        return MapLibreMap(center=[20, 0], zoom=2)

    def toggle_sidebar(self, *args: Any, **kwargs: Any) -> None:
        """
        Toggles the visibility of the sidebar.

        Args:
            *args (Any): Additional positional arguments.
            **kwargs (Any): Additional keyword arguments.
        """
        self.sidebar_visible = not self.sidebar_visible
        self.toggle_icon.children = [
            "mdi-chevron-right" if self.sidebar_visible else "mdi-chevron-left"
        ]
        self.update_sidebar_content()

    def update_sidebar_content(self) -> None:
        """
        Updates the content of the sidebar based on its visibility.
        If the sidebar is visible, it displays the toggle button and the sidebar content.
        If the sidebar is hidden, it only displays the toggle button.
        """
        if self.sidebar_visible:
            # Header row: toggle on the left, settings on the right
            header_row = v.Row(
                class_="ma-0 pa-0",
                align="center",
                justify="space-between",
                children=[self.toggle_btn, self.settings_btn],
            )

            children = [header_row]

            children.append(self.sidebar_content_box)

            self.sidebar.children = children
            self.sidebar.style_ = (
                f"min-width: {self.min_width}px; max-width: {self.max_width}px;"
            )
        else:
            self.sidebar.children = [self.toggle_btn]
            self.sidebar.style_ = "width: 48px; min-width: 48px; max-width: 48px;"

    def set_sidebar_content(
        self, content: Union[widgets.VBox, List[widgets.Widget]]
    ) -> None:
        """
        Replaces all content in the sidebar (except the toggle button).

        Args:
            content (Union[widgets.VBox, List[widgets.Widget]]): The new content for the sidebar.
        """
        if isinstance(content, (list, tuple)):
            self.sidebar_content_box.children = content
        else:
            self.sidebar_content_box.children = [content]

    def add_to_sidebar(
        self,
        widget: widgets.Widget,
        add_header: bool = True,
        widget_icon: str = "mdi-tools",
        close_icon: str = "mdi-close",
        label: str = "My Tools",
        background_color: str = "#f5f5f5",
        height: str = "40px",
        expanded: bool = True,
        host_map: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """
        Appends a widget to the sidebar content.

        Args:
            widget (Optional[Union[widgets.Widget, List[widgets.Widget]]]): Initial widget(s) to display in the content box.
            widget_icon (str): Icon for the header. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            close_icon (str): Icon for the close button. See https://pictogrammers.github.io/@mdi/font/2.0.46/ for available icons.
            background_color (str): Background color of the header. Defaults to "#f5f5f5".
            label (str): Text label for the header. Defaults to "My Tools".
            height (str): Height of the header. Defaults to "40px".
            expanded (bool): Whether the panel is expanded by default. Defaults to True.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """

        if label in self.sidebar_widgets:
            self.remove_from_sidebar(name=label)

        if add_header:
            widget = CustomWidget(
                widget,
                widget_icon=widget_icon,
                close_icon=close_icon,
                label=label,
                background_color=background_color,
                height=height,
                expanded=expanded,
                host_map=host_map,
                **kwargs,
            )

        self.sidebar_content_box.children += (widget,)
        self.sidebar_widgets[label] = widget

    def remove_from_sidebar(
        self, widget: widgets.Widget = None, name: str = None
    ) -> None:
        """
        Removes a widget from the sidebar content.

        Args:
            widget (widgets.Widget): The widget to remove from the sidebar.
            name (str): The name of the widget to remove from the sidebar.
        """
        key = None
        for key, value in self.sidebar_widgets.items():
            if value == widget or key == name:
                if widget is None:
                    widget = self.sidebar_widgets[key]
                break

        if key is not None and key in self.sidebar_widgets:
            self.sidebar_widgets.pop(key)
        self.sidebar_content_box.children = tuple(
            child for child in self.sidebar_content_box.children if child != widget
        )

    def set_sidebar_width(self, min_width: int = None, max_width: int = None) -> None:
        """
        Dynamically updates the sidebar's minimum and maximum width.

        Args:
            min_width (int, optional): New minimum width in pixels. If None, keep current.
            max_width (int, optional): New maximum width in pixels. If None, keep current.
        """
        if min_width is not None:
            if isinstance(min_width, str):
                min_width = int(min_width.replace("px", ""))
            self.min_width = min_width
        if max_width is not None:
            if isinstance(max_width, str):
                max_width = int(max_width.replace("px", ""))
            self.max_width = max_width
        self.update_sidebar_content()

    def toggle_width_slider(self, *args: Any) -> None:

        if self.settings_widget not in self.sidebar_content_box.children:
            self.add_to_sidebar(self.settings_widget, add_header=False)

    def on_width_change(self, change: dict) -> None:
        new_width = change["new"]
        self.set_sidebar_width(min_width=new_width, max_width=new_width)


class LayerStyleWidget(widgets.VBox):
    """
    A widget for styling map layers interactively.

    Args:
        layer (dict): The layer to style.
        map_widget (ipyleaflet.Map or folium.Map): The map widget to update.
        widget_width (str, optional): The width of the widget. Defaults to "270px".
        label_width (str, optional): The width of the label. Defaults to "130px".
    """

    def __init__(
        self,
        layer: dict,
        map_widget: "MapLibreMap",
        widget_width: str = "270px",
        label_width: str = "130px",
    ):
        super().__init__()
        self.layer = layer
        self.map = map_widget
        self.layer_type = self._get_layer_type()
        self.layer_id = layer["layer"].id
        self.layer_paint = layer["layer"].paint
        self.original_style = self._get_current_style()
        self.widget_width = widget_width
        self.label_width = label_width

        # Create the styling widgets based on layer type
        self.style_widgets = self._create_style_widgets()

        # Create buttons
        self.apply_btn = widgets.Button(
            description="Apply",
            button_style="primary",
            tooltip="Apply style changes",
            layout=widgets.Layout(width="auto"),
        )

        self.reset_btn = widgets.Button(
            description="Reset",
            button_style="warning",
            tooltip="Reset to original style",
            layout=widgets.Layout(width="auto"),
        )

        self.close_btn = widgets.Button(
            description="Close",
            button_style="",
            tooltip="Close the widget",
            layout=widgets.Layout(width="auto"),
        )

        self.output_widget = widgets.Output()

        # Button container
        self.button_box = widgets.HBox([self.apply_btn, self.reset_btn, self.close_btn])

        # Add button callbacks
        self.apply_btn.on_click(self._apply_style)
        self.reset_btn.on_click(self._reset_style)
        self.close_btn.on_click(self._close_widget)

        # Layout
        self.layout = widgets.Layout(width="300px", padding="10px")

        # Combine all widgets
        self.children = [*self.style_widgets, self.button_box, self.output_widget]

    def _get_layer_type(self) -> str:
        """Determine the layer type."""
        return self.layer["type"]

    def _get_current_style(self) -> dict:
        """Get the current layer style."""
        return self.layer_paint

    def _create_style_widgets(self) -> List[widgets.Widget]:
        """Create style widgets based on layer type."""
        widgets_list = []

        if self.layer_type == "circle":
            widgets_list.extend(
                [
                    self._create_color_picker(
                        "Circle Color", "circle-color", "#3388ff"
                    ),
                    self._create_number_slider(
                        "Circle Radius", "circle-radius", 6, 1, 20
                    ),
                    self._create_number_slider(
                        "Circle Opacity", "circle-opacity", 0.8, 0, 1, 0.05
                    ),
                    self._create_number_slider(
                        "Circle Blur", "circle-blur", 0, 0, 1, 0.05
                    ),
                    self._create_color_picker(
                        "Circle Stroke Color", "circle-stroke-color", "#3388ff"
                    ),
                    self._create_number_slider(
                        "Circle Stroke Width", "circle-stroke-width", 1, 0, 5
                    ),
                    self._create_number_slider(
                        "Circle Stroke Opacity",
                        "circle-stroke-opacity",
                        1.0,
                        0,
                        1,
                        0.05,
                    ),
                ]
            )

        elif self.layer_type == "line":
            widgets_list.extend(
                [
                    self._create_color_picker("Line Color", "line-color", "#3388ff"),
                    self._create_number_slider("Line Width", "line-width", 2, 1, 10),
                    self._create_number_slider(
                        "Line Opacity", "line-opacity", 1.0, 0, 1, 0.05
                    ),
                    self._create_number_slider("Line Blur", "line-blur", 0, 0, 1, 0.05),
                    self._create_dropdown(
                        "Line Style",
                        "line-dasharray",
                        [
                            ("Solid", [1]),
                            ("Dashed", [2, 4]),
                            ("Dotted", [1, 4]),
                            ("Dash-dot", [2, 4, 8, 4]),
                        ],
                    ),
                ]
            )

        elif self.layer_type == "fill":
            widgets_list.extend(
                [
                    self._create_color_picker("Fill Color", "fill-color", "#3388ff"),
                    self._create_number_slider(
                        "Fill Opacity", "fill-opacity", 0.2, 0, 1, 0.05
                    ),
                    self._create_color_picker(
                        "Fill Outline Color", "fill-outline-color", "#3388ff"
                    ),
                ]
            )
        else:
            widgets_list.extend(
                [widgets.HTML(value=f"Layer type {self.layer_type} is not supported.")]
            )

        return widgets_list

    def _create_color_picker(
        self, description: str, property_name: str, default_color: str
    ) -> widgets.ColorPicker:
        """Create a color picker widget."""
        return widgets.ColorPicker(
            description=description,
            value=self.original_style.get(property_name, default_color),
            layout=widgets.Layout(
                width=self.widget_width, description_width=self.label_width
            ),
            style={"description_width": "initial"},
        )

    def _create_number_slider(
        self,
        description: str,
        property_name: str,
        default_value: float,
        min_val: float,
        max_val: float,
        step: float = 1,
    ) -> widgets.FloatSlider:
        """Create a number slider widget."""
        return widgets.FloatSlider(
            description=description,
            value=self.original_style.get(property_name, default_value),
            min=min_val,
            max=max_val,
            step=step,
            layout=widgets.Layout(
                width=self.widget_width, description_width=self.label_width
            ),
            style={"description_width": "initial"},
            continuous_update=False,
        )

    def _create_dropdown(
        self,
        description: str,
        property_name: str,
        options: List[Tuple[str, List[float]]],
    ) -> widgets.Dropdown:
        """Create a dropdown widget."""
        return widgets.Dropdown(
            description=description,
            options=options,
            value=self.original_style.get(property_name, options[0][1]),
            layout=widgets.Layout(
                width=self.widget_width, description_width=self.label_width
            ),
            style={"description_width": "initial"},
        )

    def _apply_style(self, _) -> None:
        """Apply the style changes to the layer."""
        new_style = {}

        for widget in self.style_widgets:
            if isinstance(widget, widgets.ColorPicker):
                property_name = widget.description.lower().replace(" ", "-")
                new_style[property_name] = widget.value
            elif isinstance(widget, widgets.FloatSlider):
                property_name = widget.description.lower().replace(" ", "-")
                new_style[property_name] = widget.value
            elif isinstance(widget, widgets.Dropdown):
                property_name = widget.description.lower().replace(" ", "-")
                new_style[property_name] = widget.value

        with self.output_widget:
            try:
                for key, value in new_style.items():
                    if key == "line-style":
                        key = "line-dasharray"
                    self.map.set_paint_property(self.layer["layer"].id, key, value)
            except Exception as e:
                print(e)

        self.map.layer_manager.refresh()

    def _reset_style(self, _) -> None:
        """Reset to original style."""

        # Update widgets to reflect original style
        for widget in self.style_widgets:
            if isinstance(
                widget, (widgets.ColorPicker, widgets.FloatSlider, widgets.Dropdown)
            ):
                property_name = widget.description.lower().replace(" ", "-")
                if property_name in self.original_style:
                    widget.value = self.original_style[property_name]

    def _close_widget(self, _) -> None:
        """Close the widget."""
        # self.close()
        self.map.remove_from_sidebar(name=f"Style {self.layer['layer'].id}")


class LayerManagerWidget(v.ExpansionPanels):
    """
    A widget for managing map layers.

    This widget provides controls for toggling the visibility, adjusting the opacity,
    and removing layers from a map. It also includes a master toggle to turn all layers
    on or off.

    Attributes:
        m (Map): The map object to manage layers for.
        layer_items (Dict[str, Dict[str, widgets.Widget]]): A dictionary mapping layer names
            to their corresponding control widgets (checkbox and slider).
        _building (bool): A flag indicating whether the widget is currently being built.
        master_toggle (widgets.Checkbox): A checkbox to toggle all layers on or off.
        layers_box (widgets.VBox): A container for individual layer controls.
    """

    def __init__(
        self,
        m: Any,
        expanded: bool = True,
        height: str = "40px",
        layer_icon: str = "mdi-layers",
        close_icon: str = "mdi-close",
        label="Layers",
        background_color: str = "#f5f5f5",
        groups: dict = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initializes the LayerManagerWidget.

        Args:
            m (Any): The map object to manage layers for.
            expanded (bool): Whether the expansion panel should be expanded by default. Defaults to True.
            height (str): The height of the header. Defaults to "40px".
            layer_icon (str): The icon for the layer manager. Defaults to "mdi-layers".
            close_icon (str): The icon for the close button. Defaults to "mdi-close".
            label (str): The label for the layer manager. Defaults to "Layers".
            background_color (str): The background color of the header. Defaults to "#f5f5f5".
            groups (dict): A dictionary of layer groups, such as {"Group 1": ["layer1", "layer2"],
                "Group 2": ["layer3", "layer4"]}. A group layer toggle will be created for each group.
                Defaults to None.
            *args (Any): Additional positional arguments for the parent class.
            **kwargs (Any): Additional keyword arguments for the parent class.
        """
        self.m = m
        self.layer_items = {}
        self.groups = groups
        self._building = False

        # Master toggle
        style = {"description_width": "initial"}
        self.master_toggle = widgets.Checkbox(
            value=True, description="All layers on/off", style=style
        )
        self.master_toggle.observe(self.toggle_all_layers, names="value")

        self.group_toggles = widgets.VBox()
        if isinstance(groups, dict):
            for group_name, group_layers in groups.items():
                group_toggle = widgets.Checkbox(
                    value=True,
                    description=f"{group_name} group layers on/off",
                    style=style,
                )
                group_toggle.observe(self.toggle_group_layers, names="value")
                self.group_toggles.children += (group_toggle,)

        # Build individual layer rows
        self.layers_box = widgets.VBox()
        self.build_layer_controls()

        # Close icon button
        close_btn = v.Btn(
            icon=True,
            small=True,
            class_="ma-0",
            style_="min-width: 24px; width: 24px;",
            children=[v.Icon(children=[close_icon])],
        )
        close_btn.on_event("click", self._handle_close)

        header = v.ExpansionPanelHeader(
            style_=f"height: {height}; min-height: {height}; background-color: {background_color};",
            children=[
                v.Row(
                    align="center",
                    class_="d-flex flex-grow-1 align-center",
                    children=[
                        v.Icon(children=[layer_icon], class_="ml-1"),
                        v.Spacer(),  # push title to center
                        v.Html(tag="span", children=[label], class_="text-subtitle-2"),
                        v.Spacer(),  # push close to right
                        close_btn,
                        v.Spacer(),
                    ],
                )
            ],
        )

        panel = v.ExpansionPanel(
            children=[
                header,
                v.ExpansionPanelContent(
                    children=[
                        widgets.VBox(
                            [self.master_toggle, self.group_toggles, self.layers_box]
                        )
                    ]
                ),
            ]
        )

        if expanded:
            super().__init__(
                children=[panel], v_model=[0], multiple=True, *args, **kwargs
            )
        else:
            super().__init__(children=[panel], multiple=True, *args, **kwargs)

    def _handle_close(self, widget=None, event=None, data=None):
        """Calls the on_close callback if provided."""

        self.m.remove_from_sidebar(self)
        # self.close()

    def build_layer_controls(self) -> None:
        """
        Builds the controls for individual layers.

        This method creates checkboxes for toggling visibility, sliders for adjusting opacity,
        and buttons for removing layers.
        """
        self._building = True
        self.layer_items.clear()
        rows = []

        style = {"description_width": "initial"}
        padding = "0px 5px 0px 5px"

        for name, info in list(self.m.layer_dict.items()):
            # if name == "Background":
            #     continue

            visible = info.get("visible", True)
            opacity = info.get("opacity", 1.0)

            checkbox = widgets.Checkbox(value=visible, description=name, style=style)
            checkbox.layout.max_width = "150px"

            slider = widgets.FloatSlider(
                value=opacity,
                min=0,
                max=1,
                step=0.01,
                readout=False,
                tooltip="Change layer opacity",
                layout=widgets.Layout(width="150px", padding=padding),
            )

            settings = widgets.Button(
                icon="gear",
                tooltip="Change layer style",
                layout=widgets.Layout(width="38px", height="25px", padding=padding),
            )

            remove = widgets.Button(
                icon="times",
                tooltip="Remove layer",
                layout=widgets.Layout(width="38px", height="25px", padding=padding),
            )

            def on_visibility_change(change, layer_name=name):
                self.set_layer_visibility(layer_name, change["new"])

            def on_opacity_change(change, layer_name=name):
                self.set_layer_opacity(layer_name, change["new"])

            def on_remove_clicked(btn, layer_name=name, row_ref=None):
                if layer_name == "Background":
                    for layer in self.m.get_style_layers():
                        self.m.add_call("removeLayer", layer["id"])
                else:
                    self.m.remove_layer(layer_name)
                if row_ref in self.layers_box.children:
                    self.layers_box.children = tuple(
                        c for c in self.layers_box.children if c != row_ref
                    )
                self.layer_items.pop(layer_name, None)
                if f"Style {layer_name}" in self.m.sidebar_widgets:
                    self.m.remove_from_sidebar(name=f"Style {layer_name}")

            def on_settings_clicked(btn, layer_name=name):
                style_widget = LayerStyleWidget(self.m.layer_dict[layer_name], self.m)
                self.m.add_to_sidebar(
                    style_widget,
                    widget_icon="mdi-palette",
                    label=f"Style {layer_name}",
                )

            checkbox.observe(on_visibility_change, names="value")
            slider.observe(on_opacity_change, names="value")

            row = widgets.HBox(
                [checkbox, slider, settings, remove], layout=widgets.Layout()
            )

            remove.on_click(
                lambda btn, r=row, n=name: on_remove_clicked(
                    btn, layer_name=n, row_ref=r
                )
            )

            settings.on_click(
                lambda btn, n=name: on_settings_clicked(btn, layer_name=n)
            )

            rows.append(row)
            self.layer_items[name] = {"checkbox": checkbox, "slider": slider}

        self.layers_box.children = rows
        self._building = False

    def toggle_all_layers(self, change: Dict[str, Any]) -> None:
        """
        Toggles the visibility of all layers.

        Args:
            change (Dict[str, Any]): The change event from the master toggle checkbox.
        """
        if self._building:
            return
        for name, controls in self.layer_items.items():
            controls["checkbox"].value = change["new"]

        for widget in self.group_toggles.children:
            widget.value = change["new"]

    def toggle_group_layers(self, change: Dict[str, Any]) -> None:
        """
        Toggles the visibility of a group of layers.
        """
        if self._building:
            return
        group_name = change["owner"].description.split(" ")[0]
        group_layers = self.groups[group_name]
        for layer_name in group_layers:
            self.set_layer_visibility(layer_name, change["new"])
        self.refresh()

    def set_layer_visibility(self, name: str, visible: bool) -> None:
        """
        Sets the visibility of a specific layer.

        Args:
            name (str): The name of the layer.
            visible (bool): Whether the layer should be visible.
        """
        self.m.set_visibility(name, visible)

    def set_layer_opacity(self, name: str, opacity: float) -> None:
        """
        Sets the opacity of a specific layer.

        Args:
            name (str): The name of the layer.
            opacity (float): The opacity value (0 to 1).
        """
        self.m.set_opacity(name, opacity)

    def refresh(self) -> None:
        """
        Rebuilds the UI to reflect the current layers in the map.
        """
        self.build_layer_controls()
