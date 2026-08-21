<?php
/**
 * Footer template.
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
?>
	</div><!-- /.container -->
</main>

<footer class="site-footer">
	<div class="container">
		<?php if ( get_theme_mod( 'yc_ad_code_footer', '' ) ) : ?>
			<div class="footer-ad-slot"><?php yc_ad_slot( 'footer' ); ?></div>
		<?php endif; ?>

		<div class="footer-grid">
			<div>
				<h4><?php bloginfo( 'name' ); ?></h4>
				<p class="footer-tagline">
					<?php esc_html_e( 'YoungCraze decodes internet trends, slang and viral moments — no boring explainers, just what’s actually happening online.', 'youngcraze' ); ?>
				</p>
			</div>
			<div>
				<h4><?php esc_html_e( 'Explore', 'youngcraze' ); ?></h4>
				<?php
				wp_nav_menu( array(
					'theme_location' => 'footer',
					'container'      => false,
					'fallback_cb'    => false,
					'depth'          => 1,
				) );
				?>
			</div>
			<div>
				<h4><?php esc_html_e( 'Follow', 'youngcraze' ); ?></h4>
				<ul>
					<li><a href="<?php echo esc_url( home_url( '/feed/' ) ); ?>"><?php esc_html_e( 'RSS Feed', 'youngcraze' ); ?></a></li>
				</ul>
			</div>
		</div>

		<div class="footer-bottom">
			<span>&copy; <?php echo esc_html( date_i18n( 'Y' ) ); ?> <?php bloginfo( 'name' ); ?>. <?php esc_html_e( 'All rights reserved.', 'youngcraze' ); ?></span>
			<span><?php esc_html_e( 'Decode the internet. Daily.', 'youngcraze' ); ?></span>
		</div>
	</div>
</footer>

<?php wp_footer(); ?>
</body>
</html>
