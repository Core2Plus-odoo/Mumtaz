<?php
/**
 * Shown when a query returns no posts.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
?>
<div class="no-results">
	<h1><?php esc_html_e( 'Nothing strange enough was found', 'odditytrend' ); ?></h1>
	<p><?php esc_html_e( 'Try a different search term, or browse the categories above.', 'odditytrend' ); ?></p>
	<?php get_search_form(); ?>
</div>
