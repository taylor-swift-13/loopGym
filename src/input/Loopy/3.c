// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/MAP-forward_VeriMAP_true.c
extern int unknown_int(void);

;

/*@
  requires n>= 0;
*/
void loopy_3(int n){

   int i, a, b;
   

   i = 0; 
   a = 0; 
   b = 0;

   while( i < n ){
      if(unknown_int()) {
         a = a+1;
         b = b+2;
      } else {
         a = a+2;
         b = b+1;
      }
      i = i+1;
   }

   if ( a+b != 3*n)
      goto ERROR;

return;

{ ERROR: {; 
//@ assert(\false);
}
}
}