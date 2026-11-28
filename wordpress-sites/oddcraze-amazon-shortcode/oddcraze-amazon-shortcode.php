<?php
/**
 * Plugin Name: OddCraze Amazon Shortcode
 * Description: [amz] shortcode renders an Amazon affiliate product box with the site's tag baked in, plus an automatic disclosure. No API calls, no license — ASIN/title/image/price are supplied by hand.
 * Version: 1.0.0
 * Author: Mumtaz Digital
 * Text Domain: oddcraze-amazon-shortcode
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'ODDCRAZE_AMZ_TAG', 'odditytrend03-20' );

/**
 * [amz product="ASIN" title="Product Name" image="https://..." price="$19.99"]
 */
function oddcraze_amz_shortcode( $atts ) {
	$atts = shortcode_atts( array(
		'product' => '',
		'title'   => '',
		'image'   => '',
		'price'   => '',
	), $atts, 'amz' );

	$asin = preg_replace( '/[^A-Za-z0-9]/', '', $atts['product'] );
	if ( empty( $asin ) ) {
		return '';
	}

	$url = esc_url( 'https://www.amazon.com/dp/' . $asin . '/?tag=' . ODDCRAZE_AMZ_TAG );

	ob_start();
	?>
	<div class="oddcraze-amz-box">
		<?php if ( $atts['image'] ) : ?>
			<a href="<?php echo $url; ?>" target="_blank" rel="sponsored nofollow noopener" class="oddcraze-amz-box__media">
				<img src="<?php echo esc_url( $atts['image'] ); ?>" alt="<?php echo esc_attr( $atts['title'] ); ?>" loading="lazy">
			</a>
		<?php endif; ?>
		<div class="oddcraze-amz-box__body">
			<p class="oddcraze-amz-box__title"><?php echo esc_html( $atts['title'] ); ?></p>
			<?php if ( $atts['price'] ) : ?>
				<p class="oddcraze-amz-box__price"><?php echo esc_html( $atts['price'] ); ?></p>
			<?php endif; ?>
			<a href="<?php echo $url; ?>" target="_blank" rel="sponsored nofollow noopener" class="oddcraze-amz-box__btn">View on Amazon</a>
		</div>
	</div>
	<?php
	return ob_get_clean();
}
add_shortcode( 'amz', 'oddcraze_amz_shortcode' );

/**
 * Append the affiliate disclosure once, only to posts that actually used
 * [amz] — checked against the raw post content, not shortcode-call state,
 * so it's correct regardless of how many product boxes are in the post.
 */
function oddcraze_amz_disclosure( $content ) {
	if ( ! is_singular() || ! in_the_loop() || ! is_main_query() ) {
		return $content;
	}
	if ( ! has_shortcode( get_post()->post_content, 'amz' ) ) {
		return $content;
	}
	$disclosure = '<p class="oddcraze-amz-disclosure"><em>As an Amazon Associate we earn from qualifying purchases.</em></p>';
	return $content . $disclosure;
}
add_filter( 'the_content', 'oddcraze_amz_disclosure', 20 );

function oddcraze_amz_styles() {
	?>
	<style>
		.oddcraze-amz-box { display: flex; gap: 1rem; align-items: center; border: 1px solid rgba(0,0,0,0.12); border-radius: 10px; padding: 1rem; margin: 1.5rem 0; background: rgba(0,0,0,0.02); }
		.oddcraze-amz-box__media { flex: 0 0 96px; }
		.oddcraze-amz-box__media img { width: 96px; height: 96px; object-fit: contain; border-radius: 6px; }
		.oddcraze-amz-box__body { flex: 1; min-width: 0; }
		.oddcraze-amz-box__title { font-weight: 700; margin: 0 0 0.25rem; }
		.oddcraze-amz-box__price { margin: 0 0 0.5rem; color: #b45309; font-weight: 600; }
		.oddcraze-amz-box__btn { display: inline-block; background: #ff9900; color: #111; font-weight: 700; padding: 0.5em 1.1em; border-radius: 999px; text-decoration: none; }
		.oddcraze-amz-box__btn:hover { background: #e88a00; }
		.oddcraze-amz-disclosure { font-size: 0.82rem; color: #666; border-top: 1px solid rgba(0,0,0,0.1); padding-top: 0.75rem; margin-top: 1.5rem; }
	</style>
	<?php
}
add_action( 'wp_head', 'oddcraze_amz_styles' );
