<?php
/**
 * Customizer: ad slot fields so AdSense (or any ad network) code can be
 * managed from wp-admin without editing theme files.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

function yc_customize_register( $wp_customize ) {
	$wp_customize->add_section( 'yc_ad_slots', array(
		'title'    => __( 'Ad Slots', 'youngcraze' ),
		'priority' => 200,
	) );

	$slots = array(
		'header'     => __( 'Header ad code', 'youngcraze' ),
		'in_content' => __( 'In-article ad code', 'youngcraze' ),
		'sidebar'    => __( 'Sidebar ad code', 'youngcraze' ),
		'footer'     => __( 'Footer ad code', 'youngcraze' ),
	);

	foreach ( $slots as $key => $label ) {
		$setting_id = 'yc_ad_code_' . $key;

		$wp_customize->add_setting( $setting_id, array(
			'default'           => '',
			'sanitize_callback' => 'yc_sanitize_ad_code',
			'capability'        => 'edit_theme_options',
		) );

		$wp_customize->add_control( $setting_id, array(
			'label'   => $label,
			'section' => 'yc_ad_slots',
			'type'    => 'textarea',
		) );
	}
}
add_action( 'customize_register', 'yc_customize_register' );

/**
 * Ad network snippets legitimately include <script> tags. This field is
 * restricted to users who hold 'edit_theme_options' (admins), the same
 * trust level WordPress already grants for raw theme customization.
 */
function yc_sanitize_ad_code( $code ) {
	if ( ! current_user_can( 'unfiltered_html' ) ) {
		return wp_kses_post( $code );
	}
	return $code;
}
