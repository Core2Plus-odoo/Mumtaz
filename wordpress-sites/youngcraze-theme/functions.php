<?php
/**
 * Young Craze theme setup.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'YC_THEME_VERSION', '1.0.0' );

/**
 * Theme setup: supports, menus, image sizes.
 */
function yc_setup() {
	load_theme_textdomain( 'youngcraze', get_template_directory() . '/languages' );

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
		'primary' => __( 'Primary Menu', 'youngcraze' ),
		'footer'  => __( 'Footer Menu', 'youngcraze' ),
	) );

	set_post_thumbnail_size( 800, 500, true );
	add_image_size( 'yc-featured', 1000, 620, true );
	add_image_size( 'yc-card', 500, 320, true );
	add_image_size( 'yc-trending', 400, 300, true );
}
add_action( 'after_setup_theme', 'yc_setup' );

/**
 * Enqueue styles and scripts.
 */
function yc_scripts() {
	wp_enqueue_style( 'youngcraze-style', get_stylesheet_uri(), array(), YC_THEME_VERSION );
	wp_enqueue_script( 'youngcraze-main', get_template_directory_uri() . '/assets/js/main.js', array(), YC_THEME_VERSION, true );

	if ( is_singular() && comments_open() ) {
		wp_enqueue_script( 'comment-reply' );
	}
}
add_action( 'wp_enqueue_scripts', 'yc_scripts' );

/**
 * Register sidebar widget area.
 */
function yc_widgets_init() {
	register_sidebar( array(
		'name'          => __( 'Sidebar', 'youngcraze' ),
		'id'            => 'sidebar-1',
		'before_widget' => '<div class="widget %2$s">',
		'after_widget'  => '</div>',
		'before_title'  => '<h3 class="widget-title">',
		'after_title'   => '</h3>',
	) );
}
add_action( 'widgets_init', 'yc_widgets_init' );

/**
 * Sensible excerpt defaults for card layouts.
 */
function yc_excerpt_length( $length ) {
	return 22;
}
add_filter( 'excerpt_length', 'yc_excerpt_length' );

function yc_excerpt_more( $more ) {
	return '&hellip;';
}
add_filter( 'excerpt_more', 'yc_excerpt_more' );

/**
 * Ad slots: theme hook + Customizer-managed raw code, so AdSense units
 * can be dropped in from wp-admin without touching template files.
 *
 * Usage in templates: yc_ad_slot( 'header' | 'in_content' | 'sidebar' | 'footer' );
 */
function yc_ad_slot( $location ) {
	$code = get_theme_mod( 'yc_ad_code_' . $location, '' );

	/**
	 * Allows a plugin (e.g. a dedicated ad-management plugin) to inject
	 * markup for a given slot instead of the raw Customizer field.
	 */
	$code = apply_filters( 'yc_ad_slot_' . $location, $code );

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
