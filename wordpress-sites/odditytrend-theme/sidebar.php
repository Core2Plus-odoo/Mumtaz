<?php
/**
 * Sidebar template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
if ( ! is_active_sidebar( 'sidebar-1' ) && ! get_theme_mod( 'ot_ad_code_sidebar', '' ) ) {
	return;
}
?>
<aside class="site-sidebar" aria-label="<?php esc_attr_e( 'Sidebar', 'odditytrend' ); ?>">
	<?php if ( get_theme_mod( 'ot_ad_code_sidebar', '' ) ) : ?>
		<div class="widget sidebar-ad-slot"><?php ot_ad_slot( 'sidebar' ); ?></div>
	<?php endif; ?>

	<?php if ( is_active_sidebar( 'sidebar-1' ) ) : ?>
		<?php dynamic_sidebar( 'sidebar-1' ); ?>
	<?php endif; ?>
</aside>
