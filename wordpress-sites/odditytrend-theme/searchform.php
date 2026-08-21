<?php
/**
 * Search form template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
?>
<form role="search" method="get" class="search-form" action="<?php echo esc_url( home_url( '/' ) ); ?>">
	<label class="screen-reader-text" for="ot-search-field"><?php esc_html_e( 'Search for:', 'odditytrend' ); ?></label>
	<input type="search" id="ot-search-field" class="search-field" placeholder="<?php esc_attr_e( 'Search strange stories&hellip;', 'odditytrend' ); ?>" value="<?php echo get_search_query(); ?>" name="s">
	<button type="submit" class="search-submit"><?php esc_html_e( 'Search', 'odditytrend' ); ?></button>
</form>
