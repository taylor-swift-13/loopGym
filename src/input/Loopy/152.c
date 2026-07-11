// Source: data/benchmarks/accelerating_invariant_generation/cav/20.c

int unknown1(){
    int x; return x;
}
int unknown2();
int unknown3();
int unknown4();

/*@
  requires !((x+y) != k);
*/
void loopy_152(int x, int y, int k, int i, int n)
{
     int j; 
    int m = 0;
    

    j = 0;
    while(j<=n-1) {
      if(j==i)
      {
         x++;
         y--;
      }else
      {
         y++;
         x--;
      }
	if(unknown1())
  		m = j;
      j++;
    }
    if(j < n)
      
return;

    if(x + y <= k - 1 || x + y >= k + 1 || (n >= 1 && ((m <= -1) || (m >= n))))
    {goto ERROR; { ERROR: {; 
//@ assert(\false);
}
}}
}
