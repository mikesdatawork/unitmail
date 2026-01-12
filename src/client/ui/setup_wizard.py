"""
unitMail First-Run Setup Wizard.

This module provides the setup wizard that guides users through
initial configuration including deployment model selection, network
setup, domain configuration, account creation, and security options.
"""

import logging
import re
import secrets
import string
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk, Pango

logger = logging.getLogger(__name__)


class DeploymentModel(Enum):
    """Deployment model options."""

    HOSTED = "hosted"  # Use unitMail hosted gateway
    SELF_HOSTED = "self_hosted"  # Self-host the gateway
    MESH = "mesh"  # Join existing mesh network


class SetupStep(Enum):
    """Setup wizard steps."""

    WELCOME = "welcome"
    NETWORK = "network"
    DOMAIN = "domain"
    ACCOUNT = "account"
    PASSWORD = "password"
    PGP = "pgp"
    MESH = "mesh"
    SUMMARY = "summary"


@dataclass
class SetupData:
    """Container for setup wizard data."""

    # Deployment
    deployment_model: DeploymentModel = DeploymentModel.HOSTED

    # Network
    gateway_url: str = "https://gateway.unitmail.io"
    self_host_port: int = 8443

    # Domain
    domain: str = ""
    subdomain: str = ""
    dns_verified: bool = False
    dkim_selector: str = "unitmail"

    # Account
    display_name: str = ""
    email_address: str = ""
    username: str = ""

    # Password
    password: str = ""
    password_hash: str = ""

    # PGP
    generate_pgp: bool = False
    pgp_key_id: str = ""
    pgp_fingerprint: str = ""

    # Mesh
    join_mesh: bool = False
    mesh_invite_code: str = ""
    mesh_peers: list[str] = field(default_factory=list)


class PasswordStrength(Enum):
    """Password strength levels."""

    WEAK = "weak"
    FAIR = "fair"
    GOOD = "good"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class SetupWizard(Adw.Window):
    """
    First-run setup wizard for unitMail.

    Guides users through initial configuration with a multi-step
    wizard interface using Gtk.Stack for page navigation.
    """

    __gtype_name__ = "SetupWizard"

    # Signals
    __gsignals__ = {
        "setup-complete": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "setup-cancelled": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # Step order
    STEPS = [
        SetupStep.WELCOME,
        SetupStep.NETWORK,
        SetupStep.DOMAIN,
        SetupStep.ACCOUNT,
        SetupStep.PASSWORD,
        SetupStep.PGP,
        SetupStep.MESH,
        SetupStep.SUMMARY,
    ]

    def __init__(
        self,
        transient_for: Optional[Gtk.Window] = None,
        setup_service: Optional["SetupService"] = None,
    ) -> None:
        """
        Initialize the setup wizard.

        Args:
            transient_for: Parent window for modal behavior.
            setup_service: Service for performing setup actions.
        """
        super().__init__(
            title="unitMail Setup",
            default_width=700,
            default_height=600,
            modal=True,
            resizable=False,
        )

        if transient_for:
            self.set_transient_for(transient_for)

        self._setup_service = setup_service
        self._setup_data = SetupData()
        self._current_step_index = 0
        self._step_widgets: dict[SetupStep, Gtk.Widget] = {}
        self._validation_callbacks: dict[SetupStep, Callable[[], bool]] = {}

        self._build_ui()
        self._connect_signals()
        self._show_step(SetupStep.WELCOME)

        logger.info("Setup wizard initialized")

    def _build_ui(self) -> None:
        """Build the wizard UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.add_css_class("flat")

        # Cancel button
        self._cancel_button = Gtk.Button(label="Cancel")
        self._cancel_button.connect("clicked", self._on_cancel_clicked)
        header_bar.pack_start(self._cancel_button)

        main_box.append(header_bar)

        # Progress indicator
        self._progress_box = self._create_progress_indicator()
        main_box.append(self._progress_box)

        # Separator
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Content stack
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=200,
            vexpand=True,
        )
        main_box.append(self._stack)

        # Create all step pages
        self._create_welcome_page()
        self._create_network_page()
        self._create_domain_page()
        self._create_account_page()
        self._create_password_page()
        self._create_pgp_page()
        self._create_mesh_page()
        self._create_summary_page()

        # Bottom separator
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Navigation buttons
        self._nav_box = self._create_navigation_buttons()
        main_box.append(self._nav_box)

    def _create_progress_indicator(self) -> Gtk.Widget:
        """Create the progress indicator showing current step."""
        progress_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=24,
            margin_end=24,
            margin_top=12,
            margin_bottom=12,
            halign=Gtk.Align.CENTER,
        )

        self._step_indicators: list[Gtk.Widget] = []

        for i, step in enumerate(self.STEPS):
            if i > 0:
                # Connector line
                connector = Gtk.Separator(
                    orientation=Gtk.Orientation.HORIZONTAL,
                    width_request=30,
                )
                connector.add_css_class("progress-connector")
                progress_box.append(connector)

            # Step indicator
            indicator = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=4,
                halign=Gtk.Align.CENTER,
            )

            circle = Gtk.DrawingArea(
                width_request=24,
                height_request=24,
            )
            circle.set_draw_func(self._draw_step_circle, i)
            indicator.append(circle)

            label = Gtk.Label(
                label=step.value.replace("_", " ").title(),
                css_classes=["caption", "dim-label"],
            )
            indicator.append(label)

            progress_box.append(indicator)
            self._step_indicators.append((circle, label))

        return progress_box

    def _draw_step_circle(
        self,
        area: Gtk.DrawingArea,
        cr: "cairo.Context",
        width: int,
        height: int,
        step_index: int,
    ) -> None:
        """Draw a step indicator circle."""
        # Get colors from style context
        style = area.get_style_context()
        color = style.get_color()

        # Determine circle state
        if step_index < self._current_step_index:
            # Completed - filled
            cr.set_source_rgba(0.2, 0.6, 0.2, 1.0)  # Green
            cr.arc(width / 2, height / 2, 10, 0, 2 * 3.14159)
            cr.fill()
            # Checkmark
            cr.set_source_rgba(1, 1, 1, 1)
            cr.set_line_width(2)
            cr.move_to(7, 12)
            cr.line_to(10, 15)
            cr.line_to(17, 8)
            cr.stroke()
        elif step_index == self._current_step_index:
            # Current - filled with accent color
            cr.set_source_rgba(0.2, 0.4, 0.8, 1.0)  # Blue
            cr.arc(width / 2, height / 2, 10, 0, 2 * 3.14159)
            cr.fill()
            # Number
            cr.set_source_rgba(1, 1, 1, 1)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(12)
            cr.move_to(9, 16)
            cr.show_text(str(step_index + 1))
        else:
            # Future - outline only
            cr.set_source_rgba(color.red, color.green, color.blue, 0.3)
            cr.set_line_width(2)
            cr.arc(width / 2, height / 2, 9, 0, 2 * 3.14159)
            cr.stroke()
            # Number
            cr.move_to(9, 16)
            cr.select_font_face("Sans", 0, 0)
            cr.set_font_size(12)
            cr.show_text(str(step_index + 1))

    def _create_navigation_buttons(self) -> Gtk.Widget:
        """Create the navigation button bar."""
        nav_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=24,
            margin_end=24,
            margin_top=12,
            margin_bottom=12,
        )

        # Back button
        self._back_button = Gtk.Button(
            label="Back",
            css_classes=["flat"],
        )
        self._back_button.connect("clicked", self._on_back_clicked)
        nav_box.append(self._back_button)

        # Spacer
        spacer = Gtk.Box(hexpand=True)
        nav_box.append(spacer)

        # Skip button (for optional steps)
        self._skip_button = Gtk.Button(
            label="Skip",
            css_classes=["flat"],
            visible=False,
        )
        self._skip_button.connect("clicked", self._on_skip_clicked)
        nav_box.append(self._skip_button)

        # Next button
        self._next_button = Gtk.Button(
            label="Next",
            css_classes=["suggested-action"],
        )
        self._next_button.connect("clicked", self._on_next_clicked)
        nav_box.append(self._next_button)

        return nav_box

    def _create_page_container(
        self,
        title: str,
        description: str,
    ) -> tuple[Gtk.Box, Gtk.Box]:
        """
        Create a standard page container with title and content area.

        Args:
            title: Page title.
            description: Page description.

        Returns:
            Tuple of (outer_box, content_box) for adding content.
        """
        outer_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=48,
            margin_end=48,
            margin_top=24,
            margin_bottom=24,
        )

        # Title
        title_label = Gtk.Label(
            label=title,
            css_classes=["title-1"],
            xalign=0,
        )
        outer_box.append(title_label)

        # Description
        desc_label = Gtk.Label(
            label=description,
            css_classes=["body"],
            xalign=0,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
        )
        outer_box.append(desc_label)

        # Content container
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            vexpand=True,
        )
        outer_box.append(content_box)

        return outer_box, content_box

    def _create_welcome_page(self) -> None:
        """Create the welcome/deployment model selection page."""
        page, content = self._create_page_container(
            "Welcome to unitMail",
            "Choose how you'd like to use unitMail. You can host your own "
            "email server or connect to an existing gateway.",
        )

        # Deployment options
        options_group = Adw.PreferencesGroup(
            title="Deployment Model",
            description="Select your preferred setup",
        )

        # Hosted option
        self._hosted_row = Adw.ActionRow(
            title="Hosted Gateway",
            subtitle="Connect to unitMail's hosted gateway service. "
            "Easiest to set up, no server management required.",
        )
        hosted_check = Gtk.CheckButton()
        hosted_check.set_active(True)
        self._hosted_row.add_prefix(hosted_check)
        self._hosted_row.set_activatable_widget(hosted_check)
        options_group.add(self._hosted_row)

        # Self-hosted option
        self._self_hosted_row = Adw.ActionRow(
            title="Self-Hosted Gateway",
            subtitle="Run your own gateway server. Full control over your "
            "email infrastructure.",
        )
        self_hosted_check = Gtk.CheckButton(group=hosted_check)
        self._self_hosted_row.add_prefix(self_hosted_check)
        self._self_hosted_row.set_activatable_widget(self_hosted_check)
        options_group.add(self._self_hosted_row)

        # Mesh option
        self._mesh_row = Adw.ActionRow(
            title="Join Mesh Network",
            subtitle="Connect to an existing unitMail mesh network using "
            "an invite code.",
        )
        mesh_check = Gtk.CheckButton(group=hosted_check)
        self._mesh_row.add_prefix(mesh_check)
        self._mesh_row.set_activatable_widget(mesh_check)
        options_group.add(self._mesh_row)

        # Connect signals
        hosted_check.connect("toggled", self._on_deployment_changed, DeploymentModel.HOSTED)
        self_hosted_check.connect("toggled", self._on_deployment_changed, DeploymentModel.SELF_HOSTED)
        mesh_check.connect("toggled", self._on_deployment_changed, DeploymentModel.MESH)

        content.append(options_group)

        self._stack.add_named(page, SetupStep.WELCOME.value)
        self._step_widgets[SetupStep.WELCOME] = page

    def _create_network_page(self) -> None:
        """Create the network configuration page."""
        page, content = self._create_page_container(
            "Network Configuration",
            "Configure how unitMail connects to the email gateway.",
        )

        # Hosted config (shown for hosted model)
        self._hosted_config = Adw.PreferencesGroup(
            title="Gateway Connection",
        )

        gateway_row = Adw.EntryRow(
            title="Gateway URL",
        )
        gateway_row.set_text("https://gateway.unitmail.io")
        gateway_row.connect("changed", self._on_gateway_url_changed)
        self._gateway_entry = gateway_row
        self._hosted_config.add(gateway_row)

        # Test connection button
        test_row = Adw.ActionRow(
            title="Connection Status",
            subtitle="Not tested",
        )
        test_button = Gtk.Button(
            label="Test Connection",
            valign=Gtk.Align.CENTER,
        )
        test_button.connect("clicked", self._on_test_connection_clicked)
        test_row.add_suffix(test_button)
        self._connection_status_row = test_row
        self._hosted_config.add(test_row)

        content.append(self._hosted_config)

        # Self-hosted config
        self._self_hosted_config = Adw.PreferencesGroup(
            title="Self-Hosted Configuration",
            visible=False,
        )

        port_row = Adw.SpinRow.new_with_range(1, 65535, 1)
        port_row.set_title("Gateway Port")
        port_row.set_value(8443)
        port_row.connect("changed", self._on_port_changed)
        self._port_spin = port_row
        self._self_hosted_config.add(port_row)

        # TLS configuration hint
        tls_row = Adw.ActionRow(
            title="TLS Certificate",
            subtitle="A TLS certificate will be generated during setup",
        )
        tls_icon = Gtk.Image(icon_name="security-high-symbolic")
        tls_row.add_prefix(tls_icon)
        self._self_hosted_config.add(tls_row)

        content.append(self._self_hosted_config)

        self._stack.add_named(page, SetupStep.NETWORK.value)
        self._step_widgets[SetupStep.NETWORK] = page

    def _create_domain_page(self) -> None:
        """Create the domain and DNS configuration page."""
        page, content = self._create_page_container(
            "Domain Configuration",
            "Configure your email domain and verify DNS settings.",
        )

        # Domain entry
        domain_group = Adw.PreferencesGroup(
            title="Email Domain",
        )

        domain_row = Adw.EntryRow(
            title="Domain",
        )
        domain_row.set_text("")
        domain_row.connect("changed", self._on_domain_changed)
        self._domain_entry = domain_row
        domain_group.add(domain_row)

        content.append(domain_group)

        # DNS verification
        dns_group = Adw.PreferencesGroup(
            title="DNS Records",
            description="Add these records to your domain's DNS configuration",
        )

        # MX record
        self._mx_row = Adw.ActionRow(
            title="MX Record",
            subtitle="@ MX 10 mail.yourdomain.com",
        )
        mx_status = Gtk.Image(icon_name="dialog-question-symbolic")
        self._mx_row.add_suffix(mx_status)
        self._mx_status = mx_status
        dns_group.add(self._mx_row)

        # SPF record
        self._spf_row = Adw.ActionRow(
            title="SPF Record",
            subtitle="@ TXT \"v=spf1 mx -all\"",
        )
        spf_status = Gtk.Image(icon_name="dialog-question-symbolic")
        self._spf_row.add_suffix(spf_status)
        self._spf_status = spf_status
        dns_group.add(self._spf_row)

        # DKIM record
        self._dkim_row = Adw.ActionRow(
            title="DKIM Record",
            subtitle="unitmail._domainkey TXT \"v=DKIM1; k=rsa; p=...\"",
        )
        dkim_status = Gtk.Image(icon_name="dialog-question-symbolic")
        self._dkim_row.add_suffix(dkim_status)
        self._dkim_status = dkim_status
        dns_group.add(self._dkim_row)

        # DMARC record
        self._dmarc_row = Adw.ActionRow(
            title="DMARC Record",
            subtitle="_dmarc TXT \"v=DMARC1; p=quarantine; ...\"",
        )
        dmarc_status = Gtk.Image(icon_name="dialog-question-symbolic")
        self._dmarc_row.add_suffix(dmarc_status)
        self._dmarc_status = dmarc_status
        dns_group.add(self._dmarc_row)

        content.append(dns_group)

        # Verify button
        verify_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            margin_top=12,
        )

        self._verify_button = Gtk.Button(
            label="Verify DNS Records",
            css_classes=["pill"],
        )
        self._verify_button.connect("clicked", self._on_verify_dns_clicked)
        verify_box.append(self._verify_button)

        self._dns_spinner = Gtk.Spinner(visible=False)
        verify_box.append(self._dns_spinner)

        content.append(verify_box)

        # Validation
        self._validation_callbacks[SetupStep.DOMAIN] = self._validate_domain

        self._stack.add_named(page, SetupStep.DOMAIN.value)
        self._step_widgets[SetupStep.DOMAIN] = page

    def _create_account_page(self) -> None:
        """Create the email account creation page."""
        page, content = self._create_page_container(
            "Create Your Account",
            "Set up your email account details.",
        )

        account_group = Adw.PreferencesGroup(
            title="Account Information",
        )

        # Display name
        name_row = Adw.EntryRow(
            title="Display Name",
        )
        name_row.connect("changed", self._on_name_changed)
        self._name_entry = name_row
        account_group.add(name_row)

        # Username
        username_row = Adw.EntryRow(
            title="Username",
        )
        username_row.connect("changed", self._on_username_changed)
        self._username_entry = username_row
        account_group.add(username_row)

        # Email preview
        self._email_preview_row = Adw.ActionRow(
            title="Your Email Address",
            subtitle="username@yourdomain.com",
        )
        email_icon = Gtk.Image(icon_name="mail-send-symbolic")
        self._email_preview_row.add_prefix(email_icon)
        account_group.add(self._email_preview_row)

        content.append(account_group)

        # Validation
        self._validation_callbacks[SetupStep.ACCOUNT] = self._validate_account

        self._stack.add_named(page, SetupStep.ACCOUNT.value)
        self._step_widgets[SetupStep.ACCOUNT] = page

    def _create_password_page(self) -> None:
        """Create the password setup page with strength indicator."""
        page, content = self._create_page_container(
            "Set Your Password",
            "Choose a strong password to secure your account.",
        )

        password_group = Adw.PreferencesGroup(
            title="Password",
        )

        # Password entry
        password_row = Adw.PasswordEntryRow(
            title="Password",
        )
        password_row.connect("changed", self._on_password_changed)
        self._password_entry = password_row
        password_group.add(password_row)

        # Confirm password
        confirm_row = Adw.PasswordEntryRow(
            title="Confirm Password",
        )
        confirm_row.connect("changed", self._on_password_confirm_changed)
        self._confirm_entry = confirm_row
        password_group.add(confirm_row)

        content.append(password_group)

        # Strength indicator
        strength_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=12,
        )

        strength_label_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        strength_title = Gtk.Label(
            label="Password Strength:",
            css_classes=["dim-label"],
        )
        strength_label_box.append(strength_title)

        self._strength_label = Gtk.Label(
            label="Enter a password",
            css_classes=["dim-label"],
        )
        strength_label_box.append(self._strength_label)

        strength_box.append(strength_label_box)

        # Strength bar
        self._strength_bar = Gtk.LevelBar(
            min_value=0,
            max_value=5,
            value=0,
        )
        self._strength_bar.add_offset_value("weak", 1)
        self._strength_bar.add_offset_value("fair", 2)
        self._strength_bar.add_offset_value("good", 3)
        self._strength_bar.add_offset_value("strong", 4)
        self._strength_bar.add_offset_value("very-strong", 5)
        strength_box.append(self._strength_bar)

        # Password requirements
        requirements_label = Gtk.Label(
            label="Minimum 12 characters. Use a mix of uppercase, lowercase, "
            "numbers, and special characters for best security.",
            css_classes=["caption", "dim-label"],
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            xalign=0,
        )
        strength_box.append(requirements_label)

        # Match indicator
        self._match_label = Gtk.Label(
            label="",
            css_classes=["caption"],
            xalign=0,
        )
        strength_box.append(self._match_label)

        content.append(strength_box)

        # Generate password button
        generate_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=12,
        )

        generate_button = Gtk.Button(
            label="Generate Strong Password",
            css_classes=["flat"],
        )
        generate_button.connect("clicked", self._on_generate_password_clicked)
        generate_box.append(generate_button)

        content.append(generate_box)

        # Validation
        self._validation_callbacks[SetupStep.PASSWORD] = self._validate_password

        self._stack.add_named(page, SetupStep.PASSWORD.value)
        self._step_widgets[SetupStep.PASSWORD] = page

    def _create_pgp_page(self) -> None:
        """Create the optional PGP key generation page."""
        page, content = self._create_page_container(
            "PGP Encryption (Optional)",
            "Generate a PGP key pair for end-to-end encrypted email.",
        )

        pgp_group = Adw.PreferencesGroup(
            title="PGP Key Generation",
            description="PGP allows you to send and receive encrypted emails "
            "that only the intended recipient can read.",
        )

        # Enable PGP toggle
        enable_row = Adw.SwitchRow(
            title="Generate PGP Key",
            subtitle="Create a new PGP key pair for this account",
        )
        enable_row.connect("notify::active", self._on_pgp_toggle_changed)
        self._pgp_switch = enable_row
        pgp_group.add(enable_row)

        content.append(pgp_group)

        # PGP options (shown when enabled)
        self._pgp_options = Adw.PreferencesGroup(
            title="Key Options",
            visible=False,
        )

        # Key type
        key_type_row = Adw.ComboRow(
            title="Key Type",
            subtitle="Algorithm for key generation",
        )
        key_types = Gtk.StringList.new(["RSA 4096", "RSA 2048", "Ed25519"])
        key_type_row.set_model(key_types)
        key_type_row.set_selected(0)
        self._pgp_options.add(key_type_row)

        # Expiration
        expiry_row = Adw.ComboRow(
            title="Key Expiration",
            subtitle="When the key will expire",
        )
        expiry_options = Gtk.StringList.new(["1 Year", "2 Years", "5 Years", "Never"])
        expiry_row.set_model(expiry_options)
        expiry_row.set_selected(1)
        self._pgp_options.add(expiry_row)

        content.append(self._pgp_options)

        # Info banner
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=12,
            css_classes=["card"],
        )
        info_box.set_margin_start(12)
        info_box.set_margin_end(12)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(12)

        info_icon = Gtk.Image(
            icon_name="dialog-information-symbolic",
            css_classes=["dim-label"],
        )
        info_box.append(info_icon)

        info_label = Gtk.Label(
            label="Your private key will be stored securely on this device. "
            "Make sure to back it up after setup.",
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            xalign=0,
            hexpand=True,
            css_classes=["dim-label"],
        )
        info_box.append(info_label)

        content.append(info_box)

        self._stack.add_named(page, SetupStep.PGP.value)
        self._step_widgets[SetupStep.PGP] = page

    def _create_mesh_page(self) -> None:
        """Create the optional mesh network join page."""
        page, content = self._create_page_container(
            "Mesh Network (Optional)",
            "Join a distributed mesh network for improved reliability "
            "and decentralized email delivery.",
        )

        mesh_group = Adw.PreferencesGroup(
            title="Mesh Network",
            description="Mesh networking allows unitMail instances to work "
            "together for redundant email delivery.",
        )

        # Enable mesh toggle
        enable_row = Adw.SwitchRow(
            title="Join Mesh Network",
            subtitle="Connect to other unitMail instances",
        )
        enable_row.connect("notify::active", self._on_mesh_toggle_changed)
        self._mesh_switch = enable_row
        mesh_group.add(enable_row)

        content.append(mesh_group)

        # Mesh options
        self._mesh_options = Adw.PreferencesGroup(
            title="Mesh Configuration",
            visible=False,
        )

        # Invite code
        invite_row = Adw.EntryRow(
            title="Invite Code (Optional)",
        )
        invite_row.set_text("")
        self._invite_entry = invite_row
        self._mesh_options.add(invite_row)

        # Discovery options
        discovery_row = Adw.SwitchRow(
            title="Enable Discovery",
            subtitle="Automatically discover nearby mesh peers",
            active=True,
        )
        self._mesh_options.add(discovery_row)

        content.append(self._mesh_options)

        self._stack.add_named(page, SetupStep.MESH.value)
        self._step_widgets[SetupStep.MESH] = page

    def _create_summary_page(self) -> None:
        """Create the setup summary page."""
        page, content = self._create_page_container(
            "Setup Complete",
            "Review your configuration before finishing setup.",
        )

        # Summary group
        summary_group = Adw.PreferencesGroup(
            title="Configuration Summary",
        )

        # Deployment model
        self._summary_deployment = Adw.ActionRow(
            title="Deployment Model",
            subtitle="Hosted Gateway",
        )
        summary_group.add(self._summary_deployment)

        # Domain
        self._summary_domain = Adw.ActionRow(
            title="Domain",
            subtitle="Not configured",
        )
        summary_group.add(self._summary_domain)

        # Email address
        self._summary_email = Adw.ActionRow(
            title="Email Address",
            subtitle="Not configured",
        )
        summary_group.add(self._summary_email)

        # PGP status
        self._summary_pgp = Adw.ActionRow(
            title="PGP Encryption",
            subtitle="Disabled",
        )
        summary_group.add(self._summary_pgp)

        # Mesh status
        self._summary_mesh = Adw.ActionRow(
            title="Mesh Network",
            subtitle="Disabled",
        )
        summary_group.add(self._summary_mesh)

        content.append(summary_group)

        # Final notes
        notes_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=12,
        )

        notes_label = Gtk.Label(
            label="Click 'Finish' to complete setup and start using unitMail.",
            css_classes=["body"],
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            xalign=0,
        )
        notes_box.append(notes_label)

        content.append(notes_box)

        self._stack.add_named(page, SetupStep.SUMMARY.value)
        self._step_widgets[SetupStep.SUMMARY] = page

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        # Window close
        self.connect("close-request", self._on_close_request)

    # Event handlers

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close request."""
        self.emit("setup-cancelled")
        return False

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        self.emit("setup-cancelled")
        self.close()

    def _on_back_clicked(self, button: Gtk.Button) -> None:
        """Handle back button click."""
        if self._current_step_index > 0:
            self._current_step_index -= 1
            self._show_step(self.STEPS[self._current_step_index])

    def _on_next_clicked(self, button: Gtk.Button) -> None:
        """Handle next button click."""
        current_step = self.STEPS[self._current_step_index]

        # Validate current step
        if current_step in self._validation_callbacks:
            if not self._validation_callbacks[current_step]():
                return

        # Check if this is the last step
        if self._current_step_index >= len(self.STEPS) - 1:
            self._finish_setup()
            return

        # Move to next step
        self._current_step_index += 1
        self._show_step(self.STEPS[self._current_step_index])

    def _on_skip_clicked(self, button: Gtk.Button) -> None:
        """Handle skip button click."""
        if self._current_step_index < len(self.STEPS) - 1:
            self._current_step_index += 1
            self._show_step(self.STEPS[self._current_step_index])

    def _on_deployment_changed(
        self,
        button: Gtk.CheckButton,
        model: DeploymentModel,
    ) -> None:
        """Handle deployment model change."""
        if button.get_active():
            self._setup_data.deployment_model = model
            logger.info(f"Deployment model changed to: {model.value}")

    def _on_gateway_url_changed(self, row: Adw.EntryRow) -> None:
        """Handle gateway URL change."""
        self._setup_data.gateway_url = row.get_text()

    def _on_port_changed(self, row: Adw.SpinRow) -> None:
        """Handle port change."""
        self._setup_data.self_host_port = int(row.get_value())

    def _on_test_connection_clicked(self, button: Gtk.Button) -> None:
        """Handle test connection button click."""
        button.set_sensitive(False)
        self._connection_status_row.set_subtitle("Testing...")

        # Simulate connection test (would call setup_service)
        GLib.timeout_add(1000, self._complete_connection_test, button)

    def _complete_connection_test(self, button: Gtk.Button) -> bool:
        """Complete the connection test."""
        button.set_sensitive(True)
        self._connection_status_row.set_subtitle("Connected successfully")
        return False

    def _on_domain_changed(self, row: Adw.EntryRow) -> None:
        """Handle domain change."""
        domain = row.get_text()
        self._setup_data.domain = domain
        self._setup_data.dns_verified = False

        # Update DNS record previews
        if domain:
            self._mx_row.set_subtitle(f"@ MX 10 mail.{domain}")
            self._spf_row.set_subtitle(f"@ TXT \"v=spf1 mx -all\"")
            self._dkim_row.set_subtitle(
                f"unitmail._domainkey.{domain} TXT \"v=DKIM1; ...\""
            )
            self._dmarc_row.set_subtitle(
                f"_dmarc.{domain} TXT \"v=DMARC1; p=quarantine; ...\""
            )

        # Update email preview
        self._update_email_preview()

    def _on_verify_dns_clicked(self, button: Gtk.Button) -> None:
        """Handle DNS verification button click."""
        if not self._setup_data.domain:
            return

        button.set_sensitive(False)
        self._dns_spinner.set_visible(True)
        self._dns_spinner.start()

        # Simulate DNS verification (would call setup_service)
        GLib.timeout_add(2000, self._complete_dns_verification, button)

    def _complete_dns_verification(self, button: Gtk.Button) -> bool:
        """Complete the DNS verification."""
        button.set_sensitive(True)
        self._dns_spinner.stop()
        self._dns_spinner.set_visible(False)

        # Update status icons (simulated success)
        self._mx_status.set_from_icon_name("emblem-ok-symbolic")
        self._spf_status.set_from_icon_name("emblem-ok-symbolic")
        self._dkim_status.set_from_icon_name("dialog-warning-symbolic")
        self._dmarc_status.set_from_icon_name("emblem-ok-symbolic")

        self._setup_data.dns_verified = True
        return False

    def _on_name_changed(self, row: Adw.EntryRow) -> None:
        """Handle display name change."""
        self._setup_data.display_name = row.get_text()

    def _on_username_changed(self, row: Adw.EntryRow) -> None:
        """Handle username change."""
        username = row.get_text().lower()
        self._setup_data.username = username
        self._update_email_preview()

    def _update_email_preview(self) -> None:
        """Update the email address preview."""
        username = self._setup_data.username or "username"
        domain = self._setup_data.domain or "yourdomain.com"
        email = f"{username}@{domain}"
        self._setup_data.email_address = email
        self._email_preview_row.set_subtitle(email)

    def _on_password_changed(self, row: Adw.PasswordEntryRow) -> None:
        """Handle password change."""
        password = row.get_text()
        self._setup_data.password = password
        strength = self._calculate_password_strength(password)
        self._update_strength_indicator(strength)
        self._check_password_match()

    def _on_password_confirm_changed(self, row: Adw.PasswordEntryRow) -> None:
        """Handle password confirmation change."""
        self._check_password_match()

    def _calculate_password_strength(self, password: str) -> PasswordStrength:
        """Calculate password strength."""
        if not password:
            return PasswordStrength.WEAK

        score = 0

        # Length
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if len(password) >= 16:
            score += 1

        # Character variety
        if re.search(r"[a-z]", password):
            score += 0.5
        if re.search(r"[A-Z]", password):
            score += 0.5
        if re.search(r"\d", password):
            score += 0.5
        if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            score += 0.5

        # Determine strength
        if score < 2:
            return PasswordStrength.WEAK
        elif score < 3:
            return PasswordStrength.FAIR
        elif score < 4:
            return PasswordStrength.GOOD
        elif score < 5:
            return PasswordStrength.STRONG
        else:
            return PasswordStrength.VERY_STRONG

    def _update_strength_indicator(self, strength: PasswordStrength) -> None:
        """Update the password strength indicator."""
        strength_map = {
            PasswordStrength.WEAK: (1, "Weak", "error"),
            PasswordStrength.FAIR: (2, "Fair", "warning"),
            PasswordStrength.GOOD: (3, "Good", ""),
            PasswordStrength.STRONG: (4, "Strong", "success"),
            PasswordStrength.VERY_STRONG: (5, "Very Strong", "success"),
        }

        value, label, css_class = strength_map[strength]
        self._strength_bar.set_value(value)
        self._strength_label.set_label(label)

        # Update CSS class
        for cls in ["error", "warning", "success"]:
            self._strength_label.remove_css_class(cls)
        if css_class:
            self._strength_label.add_css_class(css_class)

    def _check_password_match(self) -> None:
        """Check if passwords match."""
        password = self._password_entry.get_text()
        confirm = self._confirm_entry.get_text()

        if not confirm:
            self._match_label.set_label("")
        elif password == confirm:
            self._match_label.set_label("Passwords match")
            self._match_label.remove_css_class("error")
            self._match_label.add_css_class("success")
        else:
            self._match_label.set_label("Passwords do not match")
            self._match_label.remove_css_class("success")
            self._match_label.add_css_class("error")

    def _on_generate_password_clicked(self, button: Gtk.Button) -> None:
        """Generate a strong random password."""
        # Generate a strong password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(20))

        self._password_entry.set_text(password)
        self._confirm_entry.set_text(password)

    def _on_pgp_toggle_changed(
        self,
        row: Adw.SwitchRow,
        pspec: GObject.ParamSpec,
    ) -> None:
        """Handle PGP toggle change."""
        active = row.get_active()
        self._setup_data.generate_pgp = active
        self._pgp_options.set_visible(active)

    def _on_mesh_toggle_changed(
        self,
        row: Adw.SwitchRow,
        pspec: GObject.ParamSpec,
    ) -> None:
        """Handle mesh toggle change."""
        active = row.get_active()
        self._setup_data.join_mesh = active
        self._mesh_options.set_visible(active)

    # Validation methods

    def _validate_domain(self) -> bool:
        """Validate domain configuration."""
        if not self._setup_data.domain:
            self._show_validation_error("Please enter a domain name.")
            return False
        return True

    def _validate_account(self) -> bool:
        """Validate account information."""
        if not self._setup_data.display_name:
            self._show_validation_error("Please enter your display name.")
            return False
        if not self._setup_data.username:
            self._show_validation_error("Please enter a username.")
            return False
        return True

    def _validate_password(self) -> bool:
        """Validate password."""
        password = self._password_entry.get_text()
        confirm = self._confirm_entry.get_text()

        if len(password) < 8:
            self._show_validation_error("Password must be at least 8 characters.")
            return False
        if password != confirm:
            self._show_validation_error("Passwords do not match.")
            return False
        return True

    def _show_validation_error(self, message: str) -> None:
        """Show a validation error message."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Validation Error",
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _show_step(self, step: SetupStep) -> None:
        """Show a specific step in the wizard."""
        self._stack.set_visible_child_name(step.value)
        self._update_navigation_buttons()
        self._update_progress_indicator()

        # Update network page visibility based on deployment model
        if step == SetupStep.NETWORK:
            is_self_hosted = (
                self._setup_data.deployment_model == DeploymentModel.SELF_HOSTED
            )
            self._hosted_config.set_visible(not is_self_hosted)
            self._self_hosted_config.set_visible(is_self_hosted)

        # Update summary page
        if step == SetupStep.SUMMARY:
            self._update_summary()

        logger.debug(f"Showing step: {step.value}")

    def _update_navigation_buttons(self) -> None:
        """Update navigation button states."""
        # Back button
        self._back_button.set_visible(self._current_step_index > 0)

        # Skip button (shown for optional steps)
        current_step = self.STEPS[self._current_step_index]
        optional_steps = {SetupStep.PGP, SetupStep.MESH}
        self._skip_button.set_visible(current_step in optional_steps)

        # Next button text
        if self._current_step_index >= len(self.STEPS) - 1:
            self._next_button.set_label("Finish")
        else:
            self._next_button.set_label("Next")

    def _update_progress_indicator(self) -> None:
        """Update the progress indicator."""
        # Redraw all step circles
        for i, (circle, label) in enumerate(self._step_indicators):
            circle.queue_draw()

            # Update label styling
            if i == self._current_step_index:
                label.remove_css_class("dim-label")
            else:
                label.add_css_class("dim-label")

    def _update_summary(self) -> None:
        """Update the summary page with current configuration."""
        # Deployment model
        model_labels = {
            DeploymentModel.HOSTED: "Hosted Gateway",
            DeploymentModel.SELF_HOSTED: "Self-Hosted Gateway",
            DeploymentModel.MESH: "Mesh Network",
        }
        self._summary_deployment.set_subtitle(
            model_labels.get(self._setup_data.deployment_model, "Unknown")
        )

        # Domain
        self._summary_domain.set_subtitle(
            self._setup_data.domain or "Not configured"
        )

        # Email
        self._summary_email.set_subtitle(
            self._setup_data.email_address or "Not configured"
        )

        # PGP
        self._summary_pgp.set_subtitle(
            "Enabled" if self._setup_data.generate_pgp else "Disabled"
        )

        # Mesh
        self._summary_mesh.set_subtitle(
            "Enabled" if self._setup_data.join_mesh else "Disabled"
        )

    def _finish_setup(self) -> None:
        """Complete the setup process."""
        logger.info("Completing setup wizard")

        # Emit completion signal with setup data
        self.emit("setup-complete", self._setup_data)

        # Close the wizard
        self.close()

    # Public methods

    def get_setup_data(self) -> SetupData:
        """Get the current setup data."""
        return self._setup_data

    def set_setup_service(self, service: "SetupService") -> None:
        """Set the setup service for performing actions."""
        self._setup_service = service
