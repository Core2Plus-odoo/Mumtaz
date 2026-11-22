<?php
/**
 * Header template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
	<meta charset="<?php bloginfo( 'charset' ); ?>">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<?php wp_body_open(); ?>

<header class="site-header">
	<div class="container site-header__bar">
		<div class="site-branding">
			<?php if ( has_custom_logo() ) : ?>
				<?php the_custom_logo(); ?>
			<?php else : ?>
				<p class="site-title"><a href="<?php echo esc_url( home_url( '/' ) ); ?>" rel="home"><?php bloginfo( 'name' ); ?></a></p>
			<?php endif; ?>
		</div>

		<button class="menu-toggle" aria-controls="primary-menu" aria-expanded="false">
			<?php esc_html_e( 'Menu', 'youngcraze' ); ?>
		</button>

		<nav class="primary-nav" id="primary-menu" aria-label="<?php esc_attr_e( 'Primary', 'youngcraze' ); ?>">
			<?php
			wp_nav_menu( array(
				'theme_location' => 'primary',
				'container'      => false,
				'fallback_cb'    => false,
			) );
			?>
		</nav>
	</div>
	<?php if ( get_theme_mod( 'yc_ad_code_header', '' ) ) : ?>
		<div class="header-ad-slot">
			<div class="container"><?php yc_ad_slot( 'header' ); ?></div>
		</div>
	<?php endif; ?>
</header>

<main class="site-main" id="main">
	<div class="container">
