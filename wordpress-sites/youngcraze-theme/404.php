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
	<h1><?php esc_html_e( "404: This trend doesn't exist", 'youngcraze' ); ?></h1>
	<p><?php esc_html_e( "The page you're looking for isn't here. It probably never went viral.", 'youngcraze' ); ?></p>
	<?php get_search_form(); ?>
</div>
<?php get_footer(); ?>
