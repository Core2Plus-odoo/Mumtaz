<?php
/**
 * Sidebar template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
if ( ! is_active_sidebar( 'sidebar-1' ) && ! get_theme_mod( 'yc_ad_code_sidebar', '' ) ) {
	return;
}
?>
<aside class="site-sidebar" aria-label="<?php esc_attr_e( 'Sidebar', 'youngcraze' ); ?>">
	<div class="slang-cta">
		<h3><?php esc_html_e( 'Lost in the slang?', 'youngcraze' ); ?></h3>
		<p><?php esc_html_e( "We explain it before it's cringe. New terms decoded every week.", 'youngcraze' ); ?></p>
	</div>

	<?php if ( get_theme_mod( 'yc_ad_code_sidebar', '' ) ) : ?>
		<div class="widget sidebar-ad-slot"><?php yc_ad_slot( 'sidebar' ); ?></div>
	<?php endif; ?>

	<?php if ( is_active_sidebar( 'sidebar-1' ) ) : ?>
		<?php dynamic_sidebar( 'sidebar-1' ); ?>
	<?php endif; ?>
</aside>
