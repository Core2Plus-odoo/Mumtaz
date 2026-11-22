<?php
/**
 * Search form template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
?>
<form role="search" method="get" class="search-form" action="<?php echo esc_url( home_url( '/' ) ); ?>">
	<label class="screen-reader-text" for="yc-search-field"><?php esc_html_e( 'Search for:', 'youngcraze' ); ?></label>
	<input type="search" id="yc-search-field" class="search-field" placeholder="<?php esc_attr_e( 'Search trends, slang, drama&hellip;', 'youngcraze' ); ?>" value="<?php echo get_search_query(); ?>" name="s">
	<button type="submit" class="search-submit"><?php esc_html_e( 'Search', 'youngcraze' ); ?></button>
</form>
