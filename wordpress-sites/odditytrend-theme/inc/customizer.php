<?php
/**
 * Customizer: ad slot fields so AdSense (or any ad network) code can be
 * managed from wp-admin without editing theme files.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

function ot_customize_register( $wp_customize ) {
	$wp_customize->add_section( 'ot_ad_slots', array(
		'title'    => __( 'Ad Slots', 'odditytrend' ),
		'priority' => 200,
	) );

	$slots = array(
		'header'     => __( 'Header ad code', 'odditytrend' ),
		'in_content' => __( 'In-article ad code', 'odditytrend' ),
		'sidebar'    => __( 'Sidebar ad code', 'odditytrend' ),
		'footer'     => __( 'Footer ad code', 'odditytrend' ),
	);

	foreach ( $slots as $key => $label ) {
		$setting_id = 'ot_ad_code_' . $key;

		$wp_customize->add_setting( $setting_id, array(
			'default'           => '',
			'sanitize_callback' => 'ot_sanitize_ad_code',
			'capability'        => 'edit_theme_options',
		) );

		$wp_customize->add_control( $setting_id, array(
			'label'   => $label,
			'section' => 'ot_ad_slots',
			'type'    => 'textarea',
		) );
	}
}
add_action( 'customize_register', 'ot_customize_register' );

/**
 * Ad network snippets legitimately include <script> tags. This field is
 * restricted to users who hold 'edit_theme_options' (admins), the same
 * trust level WordPress already grants for raw theme customization.
 */
function ot_sanitize_ad_code( $code ) {
	if ( ! current_user_can( 'unfiltered_html' ) ) {
		return wp_kses_post( $code );
	}
	return $code;
}
