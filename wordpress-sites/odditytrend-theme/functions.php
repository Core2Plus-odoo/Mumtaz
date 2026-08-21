<?php
/**
 * Oddity Trend theme setup.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'OT_THEME_VERSION', '1.0.0' );

/**
 * Theme setup: supports, menus, image sizes.
 */
function ot_setup() {
	load_theme_textdomain( 'odditytrend', get_template_directory() . '/languages' );

	add_theme_support( 'automatic-feed-links' );
	add_theme_support( 'title-tag' );
	add_theme_support( 'post-thumbnails' );
	add_theme_support( 'html5', array( 'search-form', 'comment-form', 'comment-list', 'gallery', 'caption', 'style', 'script' ) );
	add_theme_support( 'custom-logo', array(
		'height'      => 60,
		'width'       => 200,
		'flex-height' => true,
		'flex-width'  => true,
	) );
	add_theme_support( 'responsive-embeds' );

	register_nav_menus( array(
		'primary' => __( 'Primary Menu', 'odditytrend' ),
		'footer'  => __( 'Footer Menu', 'odditytrend' ),
	) );

	set_post_thumbnail_size( 800, 500, true );
	add_image_size( 'ot-featured', 1000, 620, true );
	add_image_size( 'ot-card', 500, 320, true );
}
add_action( 'after_setup_theme', 'ot_setup' );

/**
 * Enqueue styles and scripts.
 */
function ot_scripts() {
	wp_enqueue_style( 'odditytrend-style', get_stylesheet_uri(), array(), OT_THEME_VERSION );
	wp_enqueue_script( 'odditytrend-main', get_template_directory_uri() . '/assets/js/main.js', array(), OT_THEME_VERSION, true );

	if ( is_singular() && comments_open() ) {
		wp_enqueue_script( 'comment-reply' );
	}
}
add_action( 'wp_enqueue_scripts', 'ot_scripts' );

/**
 * Register sidebar widget area.
 */
function ot_widgets_init() {
	register_sidebar( array(
		'name'          => __( 'Sidebar', 'odditytrend' ),
		'id'            => 'sidebar-1',
		'before_widget' => '<div class="widget %2$s">',
		'after_widget'  => '</div>',
		'before_title'  => '<h3 class="widget-title">',
		'after_title'   => '</h3>',
	) );
}
add_action( 'widgets_init', 'ot_widgets_init' );

/**
 * Sensible excerpt defaults for card layouts.
 */
function ot_excerpt_length( $length ) {
	return 26;
}
add_filter( 'excerpt_length', 'ot_excerpt_length' );

function ot_excerpt_more( $more ) {
	return '&hellip;';
}
add_filter( 'excerpt_more', 'ot_excerpt_more' );

/**
 * Ad slots: theme hook + Customizer-managed raw code, so AdSense units
 * can be dropped in from wp-admin without touching template files.
 *
 * Usage in templates: ot_ad_slot( 'header' | 'in_content' | 'sidebar' | 'footer' );
 */
function ot_ad_slot( $location ) {
	$code = get_theme_mod( 'ot_ad_code_' . $location, '' );

	/**
	 * Allows a plugin (e.g. a dedicated ad-management plugin) to inject
	 * markup for a given slot instead of the raw Customizer field.
	 */
	$code = apply_filters( 'ot_ad_slot_' . $location, $code );

	if ( empty( $code ) ) {
		return;
	}

	echo '<div class="' . esc_attr( str_replace( '_', '-', $location ) ) . '-ad-slot ad-slot" data-ad-slot="' . esc_attr( $location ) . '">';
	// Ad network code is entered by a trusted site admin via the Customizer, intentionally unescaped.
	echo $code; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
	echo '</div>';
}

require get_template_directory() . '/inc/template-tags.php';
require get_template_directory() . '/inc/customizer.php';
