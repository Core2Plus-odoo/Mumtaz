<?php
/**
 * 404 template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
get_header();
?>
<div class="no-results">
	<h1><?php esc_html_e( '404: This is stranger than usual', 'odditytrend' ); ?></h1>
	<p><?php esc_html_e( "The page you're looking for doesn't exist. Maybe it's a genuine mystery.", 'odditytrend' ); ?></p>
	<?php get_search_form(); ?>
</div>
<?php get_footer(); ?>
